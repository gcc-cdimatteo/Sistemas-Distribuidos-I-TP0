package common

import (
	"bufio"
	"bytes"
	"encoding/binary"
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
		c.lives = false
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
func (c *Client) StartClientLoop() error {
	go c.HandleShutdown()

	log.Debugf("action: open file | result: in progress | client_id: %v", c.config.ID)

	filePath := fmt.Sprintf("/dataset/agency-%v.csv", c.config.ID)
	file, err := os.Open(filePath)
	if err != nil {
		log.Errorf("could not open file %s: %v", filePath, err)
		return err
	}

	log.Debugf("action: open file | result: success | client_id: %v", c.config.ID)

	defer file.Close()

	reader := bufio.NewReader(file)

	log.Debugf("action: bets send | result: in progress | client_id: %v", c.config.ID)

	// Start client connecion
	err = c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("server socket closed or client no longer lives")
		return fmt.Errorf("server socket closed or client no longer lives")
	}

	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
		c.lives = false
		return err
	}

	err = c.SendBets(reader)

	if err != nil {
		log.Criticalf("action: bets send | result: fail | client_id: %v", c.config.ID)
		return err
	}

	log.Debugf("action: bets send | result: success | client_id: %v", c.config.ID)

	winners, err := c.Send(fmt.Sprintf("CON|%v", c.config.ID))

	if err != nil {
		log.Criticalf("action: consulta_ganadores | result: fail | error: %v", err)
		return err
	}

	if winners == "\n" {
		log.Infof("action: consulta_ganadores | result: success | cant_ganadores: 0")
	} else {
		log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %v", len(strings.Split(winners, "|")))
	}

	c.conn.Close()

	return nil
}

func (c *Client) SendBets(reader *bufio.Reader) error {
	lastBatch := NewBatch()

	for {
		if !c.lives {
			log.Criticalf("action: batch process | result: fail | client_id: %v | error: connection closed", c.config.ID)
			return fmt.Errorf("client no longer lives")
		}

		line, err := reader.ReadString('\n')

		if err == io.EOF {
			c.SendBatch(lastBatch)
			time.Sleep(c.config.BatchSleep)
			_, err = c.Send("END\n")
			if err != nil {
				return err
			}
			break
		}

		if err != nil {
			return err
		}

		lineSplitted := strings.Split(strings.TrimSpace(line), ",")

		if len(lineSplitted) < 5 {
			continue
		}

		bet := Bet{
			agencia:    c.config.ID,
			nombre:     lineSplitted[0],
			apellido:   lineSplitted[1],
			documento:  lineSplitted[2],
			nacimiento: lineSplitted[3],
			numero:     lineSplitted[4],
		}

		if !lastBatch.CanHandle(bet, c.config.BatchMaxAmount) {
			c.SendBatch(lastBatch)
			time.Sleep(c.config.BatchSleep)

			lastBatch = NewBatch()
		}

		lastBatch.AppendBet(bet)
	}

	return nil
}

func (c *Client) SendBatch(batch Batch) {
	if batch.size == 0 {
		return
	}

	log.Debugf("action: batch send | result: in progress | batch size: %v", batch.size)

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
		log.Debugf("action: batch send | result: success | batch size: %v", batch.size)
	} else {
		log.Warningf("action: batch send | result: fail | batch size: %v | error: %s", batch.size, messageReceived)
	}
}

func (c *Client) Send(message string) (string, error) {
	messageBytes := []byte(message)

	buffer := new(bytes.Buffer)

	// Message's length
	err := binary.Write(buffer, binary.BigEndian, uint32(len(messageBytes)))
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

	messageLength := buffer.Len()
	bytesSent := 0

	// Send the complete binary message
	for bytesSent < messageLength {
		n, err := c.conn.Write(buffer.Bytes())
		if err != nil {
			log.Errorf("action: send_message | result: fail | client_id: %v | error: %v", c.config.ID, err)
			return "", err
		}
		bytesSent += n
	}

	// Get Response
	messageReceived, err := c.Recv()

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
