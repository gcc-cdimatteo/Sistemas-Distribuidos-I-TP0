import sys

def main():
    args = sys.argv[1:]

    if (len(args) != 2): raise Exception("Must receive filename and amount of clients to be created")

    amount_clients = 0

    try:
        amount_clients = int(args[1])
    except:
        raise TypeError("The amount of clients to be creted must be integer")

    string_builder = ""

    string_builder += """
name: tp0
services:
  server:
    container_name: server
    image: server:latest
    entrypoint: python3 /main.py
    volumes:
      - ./server/config.ini:/config.ini
    environment:
      - PYTHONUNBUFFERED=1
      - LOGGING_LEVEL=DEBUG
    networks:
      - testing_net
    """
    
    for i in range(amount_clients):
        string_builder += f"""
  client{i+1}:
    container_name: client{i+1}
    image: client:latest
    entrypoint: /client
    volumes:
      - ./client/config.yaml:/config.yaml
    environment:
      - CLI_ID={i+1}
      - CLI_LOG_LEVEL=DEBUG
    networks:
      - testing_net
    depends_on:
      - server
        """


    string_builder += """
networks:
  testing_net:
    ipam:
      driver: default
      config:
        - subnet: 172.25.125.0/24
    """

    file = open(args[0], "w")
    file.write(string_builder)
    file.close()

    print(f"{args[0]} created successfully")

main()