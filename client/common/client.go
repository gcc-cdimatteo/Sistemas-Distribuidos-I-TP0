package common

import (
	"bytes"
	"encoding/binary"
	"encoding/csv"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID             string
	ServerAddress  string
	LoopAmount     int
	LoopPeriod     time.Duration
	BatchMaxAmount int
	BatchSleep     time.Duration
}

// Client Entity that encapsulates how
type Client struct {
	config ClientConfig
	conn   net.Conn
	term   chan os.Signal
	lives  bool
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config: config,
		term:   make(chan os.Signal, 1),
		lives:  true,
	}

	signal.Notify(client.term, syscall.SIGTERM)

	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
	}
	c.conn = conn
	return nil
}

// Handle Client Graceful Shutdown when SIGTERM is received
func (c *Client) HandleShutdown() {
	<-c.term
	log.Criticalf("action: handling shutdown | result: in progress | client_id: %v", c.config.ID)
	c.lives = false
	if c.conn != nil {
		c.conn.Close()
	}
	log.Criticalf("action: client shutdown | result: success | client_id: %v", c.config.ID)
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	go c.HandleShutdown()

	bets, err := c.GetBetData()

	if err != nil {
		log.Criticalf("action: agency file read | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return
	}

	log.Debugf("action: bets send | result: in progress | client_id: %v", c.config.ID)

	c.SendBets(bets)

	log.Debugf("action: bets send | result: success | client_id: %v", c.config.ID)

	for {
		message_received, err := c.Send("WIN\n")

		if message_received == "Y\n" {
			winners, err := c.Send(fmt.Sprintf("CON|%v", c.config.ID))

			if winners == "\n" {
				log.Infof("action: consulta_ganadores | result: success | cant_ganadores: 0")
			} else {
				log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %v", len(strings.Split(winners, "|")))
			}

			if err != nil {
				log.Criticalf("action: consulta_ganadores | result: fail | error: %v", err)
			}

			break
		}

		if err != nil {
			log.Criticalf("action: ask for winner | result: fail")
			break
		}

		time.Sleep(c.config.LoopPeriod)
	}
}

func (c *Client) GetBetData() ([]Bet, error) {
	filePath := fmt.Sprintf("/dataset/agency-%v.csv", c.config.ID)
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("could not open file %s: %v", filePath, err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	records, err := reader.ReadAll()
	if err != nil {
		return nil, fmt.Errorf("could not read CSV data: %v", err)
	}

	var bets []Bet
	for _, record := range records {
		bet := Bet{
			agencia:    c.config.ID,
			nombre:     record[0],
			apellido:   record[1],
			documento:  record[2],
			nacimiento: record[3],
			numero:     record[4],
		}
		bets = append(bets, bet)
	}

	return bets, nil
}

func (c *Client) SendBets(bets []Bet) error {
	var batches []Batch

	batches = append(batches, NewBatch())
	lastBatch := batches[len(batches)-1]

	for i, bet := range bets {
		if !c.lives {
			log.Criticalf("action: batch process | result: fail | client_id: %v | error: connection closed", c.config.ID)
			return fmt.Errorf("Client no longer lives")
		}

		if !lastBatch.CanHandle(bet, c.config.BatchMaxAmount) {
			c.SendBatch(lastBatch, len(batches))
			time.Sleep(c.config.BatchSleep)

			batches = append(batches, NewBatch())
			lastBatch = batches[len(batches)-1]
		}

		lastBatch.AppendBet(bet)

		if i == len(bets)-1 {
			c.SendBatch(lastBatch, len(batches))
			time.Sleep(c.config.BatchSleep)
			_, err := c.Send("END\n")
			return err
		}
	}

	return fmt.Errorf("final message sent with error")
}

func (c *Client) SendBatch(batch Batch, batchNumber int) {
	log.Debugf("action: batch send | result: in progress | batch n°: %v", batchNumber)

	message := batch.Serialize()

	messageReceived, err := c.Send(message)

	if err != nil {
		log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
		c.config.ID,
		messageReceived,
	)

	if messageReceived == "ACK\n" {
		log.Debugf("action: batch send | result: success | batch n°: %v", batchNumber)
	} else {
		log.Warningf("action: batch send | result: fail | batch n°: %v | error: %s", batchNumber, messageReceived)
	}
}

func (c *Client) Send(message string) (string, error) {
	err := c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("action: client no longer lives | client_id: %v", c.config.ID)
		return "", fmt.Errorf("Client no longer lives")
	}

	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return "", err
	}

	messageBytes := []byte(message)

	buffer := new(bytes.Buffer)

	// Message's length
	err = binary.Write(buffer, binary.BigEndian, uint32(len(messageBytes)))
	if err != nil {
		log.Errorf("action: write_length | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return "", err
	}

	// Message in Bytes
	err = binary.Write(buffer, binary.BigEndian, messageBytes)
	if err != nil {
		log.Errorf("action: write_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return "", err
	}

	// Send the complete binary message
	_, err = c.conn.Write(buffer.Bytes())
	if err != nil {
		log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return "", err
	}

	// Get Response
	messageReceived, err := c.Recv()

	c.conn.Close()

	if err != nil {
		log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return "", err
	}

	log.Infof("action: receive_message | result: success | client_id: %v | msg: %v", c.config.ID, messageReceived)

	return messageReceived, nil
}

func (c *Client) Recv() (string, error) {
	// Get the first 4 bytes for Message's Length
	lengthBuffer := make([]byte, 4)

	_, err := io.ReadFull(c.conn, lengthBuffer)
	if err != nil {
		return "", err
	}

	messageLength := int(binary.BigEndian.Uint32(lengthBuffer))

	// Receive the Full Message
	message := make([]byte, messageLength)

	_, err = io.ReadFull(c.conn, message)
	if err != nil {
		return "", err
	}

	return string(message), nil
}
