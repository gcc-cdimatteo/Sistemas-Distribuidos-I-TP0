package common

// Batch Entity
type Batch struct {
	bets   []Bet
	size   int
	weight int
}

func (b *Batch) AppendBet(bet Bet) {
	b.bets = append(b.bets, bet)
	b.size++
	b.weight += bet.Weight()
}

func (b *Batch) Serialize() string {
	var res string
	for _, bet := range b.bets {
		res += bet.Serialize()
	}
	return res
}

func (b *Batch) CanHandle(bet Bet, batchMaxAmount int) bool {
	return !(b.size+1 > batchMaxAmount || float64(b.weight+bet.Weight())/1024.0 > 8)
}

func (b *Batch) IsFull(batchMaxAmount int) bool {
	return b.size+1 > batchMaxAmount || float64(b.weight)/1024.0 > 8
}

func NewBatch() Batch {
	return Batch{
		bets:   []Bet{},
		size:   0,
		weight: 0,
	}
}
