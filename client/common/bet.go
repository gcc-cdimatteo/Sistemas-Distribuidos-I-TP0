package common

import (
	"fmt"
)

// Bet Entity
type Bet struct {
	agencia    int
	nombre     string
	apellido   string
	documento  string
	nacimiento string
	numero     string
}

func (b *Bet) Weight() int {
	return len(b.Serialize())
}

func (b *Bet) Serialize() string {
	return fmt.Sprintf("%v|%s|%s|%s|%s|%s\n", b.agencia, b.nombre, b.apellido, b.documento, b.nacimiento, b.numero)
}
