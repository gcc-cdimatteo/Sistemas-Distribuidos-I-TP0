MSG='Testing Message From SH'

NETWORK_INSPECT=$(docker network inspect tp0_testing_net)
SERVER_IP=$(echo "$NETWORK_INSPECT" | awk -F'"' '/"Name": "server"/ {getline; getline; getline; print $4}' | cut -d'/' -f1)

RESPONSE=$(echo $MSG | docker run --rm --platform linux/amd64 --network=tp0_testing_net -i subfuzion/netcat $SERVER_IP 12345)

if [ "$RESPONSE" == "$MSG" ]; then echo "action: test_echo_server | result: success"
else echo "action: test_echo_server | result: fail"
fi