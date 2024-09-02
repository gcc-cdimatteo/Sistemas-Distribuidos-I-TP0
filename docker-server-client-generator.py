import sys
import re

def get_client_log_level() -> str:
  with open('./client/config.yaml', 'r') as file:
    content = file.read()
    match = re.search(r'log:\s*level:\s*"(.*?)"', content)
    if match:
      return match.group(1)
    else:
      return "DEBUG"

def get_server_log_level() -> str:
  with open('./server/config.ini', 'r') as file:
    lines = file.readlines()
    for line in lines:
        if line.startswith('LOGGING_LEVEL'):
            return line.split('=')[1].strip()
  return "DEBUG"

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
    environment:
      - PYTHONUNBUFFERED=1
      - LOGGING_LEVEL={get_server_log_level()}
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
    environment:
      - CLI_ID=1
      - CLI_LOG_LEVEL={get_client_log_level()}
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