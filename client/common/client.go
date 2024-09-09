package common

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
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
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
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

	err = c.SendBets(bets)

	if err != nil {
		log.Criticalf("action: bets send | result: fail | client_id: %v", c.config.ID)
		return
	}
}

func (c *Client) GetBetData() ([]Bet, error) {
	nombre := os.Getenv("NOMBRE")
	apellido := os.Getenv("APELLIDO")
	documento := os.Getenv("DOCUMENTO")
	nacimiento := os.Getenv("NACIMIENTO")
	numero := os.Getenv("NUMERO")

	var bets []Bet
	bets = append(bets, Bet{
		agencia:    c.config.ID,
		nombre:     nombre,
		apellido:   apellido,
		documento:  documento,
		nacimiento: nacimiento,
		numero:     numero,
	})

	log.Debugf("action: bet created | result: success | bet: %v", bets[0])

	return bets, nil
}

func (c *Client) SendBets(bets []Bet) error {
	for _, bet := range bets {
		if !c.lives {
			log.Criticalf("action: batch process | result: fail | client_id: %v | error: connection closed", c.config.ID)
			return fmt.Errorf("client no longer lives")
		}

		message_received, err := c.Send(bet.Serialize())

		if message_received == bet.Serialize() {
			log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
				bet.documento,
				bet.numero,
			)
		} else {
			log.Debugf("message_sent: [%s] vs message_received: [%s]", bet.Serialize(), message_received)
		}

		if err != nil {
			log.Infof("action: apuesta_enviada | result: fail | dni: %s | numero: %s | error: %s", bet.documento, bet.numero, err)
		}

		time.Sleep(c.config.LoopPeriod)
	}

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)

	return nil
}

func (c *Client) Send(message string) (string, error) {
	err := c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("server socket closed or client no longer lives")
		return "", fmt.Errorf("server socket closed or client no longer lives")
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
