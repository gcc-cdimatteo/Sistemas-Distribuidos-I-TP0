package common

import (
	"bufio"
	"encoding/binary"
	"encoding/csv"
	"fmt"
	"net"
	"os"
	"os/signal"
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

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	go c.HandleShutdown()

	bets, err := c.GetBetData()

	if err != nil {
		log.Criticalf("action: agency file read | result: fail | client_id: %v | error: %v", c.config.ID, err)
		return
	}

	var batches []Batch

	batches = append(batches, Batch{
		bets:   []Bet{},
		size:   0,
		weight: 0,
	})

	log.Debugf("ABOUT TO SEND %v BETS", len(bets))

	for i, bet := range bets {
		if !c.lives {
			log.Criticalf("action: batch process | result: fail | client_id: %v | error: Connection Closed", c.config.ID)
			return
		}

		log.Debugf("action: bet add to batch process | result: in progress | batch n°: %v", len(batches))

		bet := batches[len(batches)-1].AppendBet(bet, c.config.BatchMaxAmount)

		if bet == nil && i == len(bets)-1 {
			log.Debugf("action: last batch sent | result: in progress | batch n°: %v", len(batches))

			c.SendBatch(batches[len(batches)-1])

			log.Debugf("action: batch sent | result: success | batch n°: %v", len(batches))

			// c.NotifyEnd()
		} else if bet != nil {
			log.Debugf("action: batch sent | result: in progress | batch n°: %v", len(batches))

			c.SendBatch(batches[len(batches)-1])

			log.Debugf("action: batch sent | result: success | batch n°: %v", len(batches))

			time.Sleep(c.config.BatchSleep)

			newBatch := Batch{
				bets:   []Bet{},
				size:   0,
				weight: 0,
			}
			newBatch.AppendBet(*bet, c.config.BatchMaxAmount)
			batches = append(batches, newBatch)
		}
	}

	log.Infof("action: batch process | result: success | client_id: %v", c.config.ID)
}

func (c *Client) HandleShutdown() {
	<-c.term
	log.Criticalf("action: handling shutdown | result: in progress | client_id: %v", c.config.ID)
	c.lives = false
	if c.conn != nil {
		c.conn.Close()
	}
	log.Criticalf("action: client shutdown | result: success | client_id: %v", c.config.ID)
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

func (c *Client) SendBatch(batch Batch) {
	err := c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("action: client no longer lives | client_id: %v", c.config.ID)
		c.lives = false
		return
	}

	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v", c.config.ID)
		c.lives = false
		return
	}

	var message string
	for _, bet := range batch.bets {
		message += bet.Serialize()
	}

	// Send Full Message Length
	err = binary.Write(c.conn, binary.BigEndian, uint32(batch.weight))
	if err != nil {
		log.Errorf("action: bet info | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	// Send Full Message
	fmt.Fprintf(c.conn, message)
	message_received, err := bufio.NewReader(c.conn).ReadString('\n')

	if err != nil {
		log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
		c.config.ID,
		message_received,
	)

	message_expected := fmt.Sprintf("BETS RECEIVED: %v", len(batch.bets))

	if message_received[:len(message_received)-1] == message_expected {
		log.Infof("action: apuesta_enviada | result: success | cantidad: %v", len(batch.bets))
	}

	c.conn.Close()
}

func (c *Client) NotifyEnd() {
	err := c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("action: client no longer lives | client_id: %v", c.config.ID)
		c.lives = false
		return
	}

	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v", c.config.ID)
		c.lives = false
		return
	}

	fmt.Fprintf(c.conn, "END\n")

	message_received, err := bufio.NewReader(c.conn).ReadString('\n')

	if err != nil {
		log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
		c.config.ID,
		message_received,
	)

	c.conn.Close()
}
