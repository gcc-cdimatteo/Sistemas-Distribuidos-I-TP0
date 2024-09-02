import sys
import re

def get_docker_compose(clients: int) -> str:
  string_builder = ""

  string_builder += f"""
name: tp0
services:
  server:
    container_name: server
    image: server:latest
    entrypoint: python3 /main.py
    volumes:
      - ./server/config.ini:/config.ini
    networks:
      - testing_net
"""
  
  for i in range(clients):
      string_builder += f"""
  client{i+1}:
    container_name: client1
    image: client:latest
    entrypoint: /client
    volumes:
      - ./client/config.yaml:/config.yaml
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
  return string_builder

def main():
    args = sys.argv[1:]

    if (len(args) != 2): raise Exception("Must receive filename and amount of clients to be created")

    try:
        amount_clients = int(args[1])
    except:
        raise TypeError("The amount of clients to be creted must be integer")
    
    docker_compose_content = get_docker_compose(amount_clients)

    with open(args[0], 'w') as compose:
      compose.write(docker_compose_content)

    print(f"{args[0]} created successfully")

main()