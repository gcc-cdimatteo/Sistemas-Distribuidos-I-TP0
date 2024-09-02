MSG='Testing Message From SH'

RESPONSE=$(echo $MSG | docker run --rm --platform linux/amd64 --network=tp0_testing_net -i subfuzion/netcat -w 5 server 12345)

if [ "$RESPONSE" == "$MSG" ]; then echo "action: test_echo_server | result: success"
else echo "action: test_echo_server | result: fail"
fi