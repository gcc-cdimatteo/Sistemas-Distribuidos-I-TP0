package common

// Batch Entity
type Batch struct {
	bets   []Bet
	size   int
	weight int
}

func (b *Batch) AppendBet(bet Bet, batchMaxAmount int) *Bet {
	if b.size+1 > batchMaxAmount || float64(b.weight+bet.Weight())/1024.0 > 8 {
		log.Debugf("Batch full: [%v] bets, [%v]b of weight", b.size, b.weight)
		return &bet
	}

	b.bets = append(b.bets, bet)
	b.size++
	b.weight += bet.Weight()

	return nil
}
