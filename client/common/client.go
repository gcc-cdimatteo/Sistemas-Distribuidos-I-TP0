package common

import (
	"bufio"
	"encoding/binary"
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

// Bet Entity
type Bet struct {
	nombre     string
	apellido   string
	documento  string
	nacimiento string
	numero     string
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

	betData := c.GetBetData()

	err := c.createClientSocket()

	if !c.lives || c.conn == nil {
		log.Criticalf("action: client no longer lives | client_id: %v", c.config.ID)
		return
	}

	if err != nil {
		log.Criticalf("action: connect | result: fail | client_id: %v", c.config.ID)
		return
	}

	// Build the message
	message := fmt.Sprintf("%v|%s|%s|%s|%s|%s\n", c.config.ID, betData.nombre, betData.apellido, betData.documento, betData.nacimiento, betData.numero)

	// Convert to 4bytes for the protocol avoiding short reads/writes
	messageLength := len(message)

	err = binary.Write(c.conn, binary.BigEndian, uint32(messageLength))
	if err != nil {
		log.Errorf("action: send_first_message | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return
	}

	// Send the message to the server
	fmt.Fprintf(c.conn, message)
	message_received, err := bufio.NewReader(c.conn).ReadString('\n')
	c.conn.Close()

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

	if message_received == message {
		log.Infof("action: apuesta_enviada | result: success | dni: %s | numero: %s",
			betData.documento,
			betData.numero,
		)
	} else {
		log.Warningf("message & message received are not equal: %s vs %s", message, message_received)
	}

	// Wait a time between sending one message and the next one
	time.Sleep(c.config.LoopPeriod)

	log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
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

func (c *Client) GetBetData() Bet {
	nombre := os.Getenv("NOMBRE")
	apellido := os.Getenv("APELLIDO")
	documento := os.Getenv("DOCUMENTO")
	nacimiento := os.Getenv("NACIMIENTO")
	numero := os.Getenv("NUMERO")

	return Bet{
		nombre:     nombre,
		apellido:   apellido,
		documento:  documento,
		nacimiento: nacimiento,
		numero:     numero,
	}
}
