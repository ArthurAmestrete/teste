import sys
import time
import socket
import random
import logging
import datetime
import threading
import zlib
import logging
from .packet import Packet
from .data_packet import DataPacket
from .token_packet import TokenPacket


class FlushingFileHandler(logging.FileHandler):
  
    def emit(self, record):        
        super().emit(record)
        self.flush()
    
class Machine:

    def __init__(self, ip: str, nickname: str, time_token: str, has_token: bool = False, 
                 error_probability: float = 0.3, TIMEOUT_VALUE: int = 100, MINIMUM_TIME: int = 2, 
                 local_ip: str = "127.0.0.1", local_port: int = 6000) -> None:
         
        # IP and Port extraction
        self.ip, self.port = self._extract_ip_and_port(ip)
        
        # Basic attributes
        self.nickname = nickname
        self.time_token = time_token
        self.error_probability = error_probability
        self.TIMEOUT_VALUE = TIMEOUT_VALUE 
        self.MINIMUM_TIME = MINIMUM_TIME
        
        # Token control attributes
        self.has_token = has_token
        self.last_token_time = None if not has_token else datetime.datetime.now()
        self.controls_token = self.has_token
        
        # Networking setup
        self.message_queue = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((local_ip, local_port))
        
        # Token generation if the machine starts with a token
        if self.has_token:
            self.generate_token()
            
        # Set up logging
        self.logger = logging.getLogger('MachineLogger')
        self.logger.setLevel(logging.DEBUG)
        fh = FlushingFileHandler(f"logs/{self.nickname}_log.log", "a")
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def start(self):
        # Define the terminate_event first
        self.terminate_event = threading.Event()

        if self.controls_token:
            self.token_checker_thread = threading.Thread(target=self.check_token_status)
            self.token_checker_thread.start()

        self.listen_thread = threading.Thread(target=self.listen_for_packets)
        self.listen_thread.start()

        # Adding a thread for user_interaction
        self.user_interaction_thread = threading.Thread(target=self.user_interaction)
        self.user_interaction_thread.start()

        self.logger.debug(f"Machine {self.nickname} started.")
        self.logger.debug('-'*50+'\n')

        if self.has_token:
            self.logger.debug(f"Machine {self.nickname} has the token. Waiting for {self.time_token} seconds\n")
            time.sleep(int(self.time_token))
            self.send_packet(self.token)
            self.has_token = False

    @staticmethod
    def _extract_ip_and_port(ip: str) -> tuple:
        ip_address, port = ip.split(":")
        return ip_address, int(port)

    def generate_token(self):
        self.token = TokenPacket()
        self.has_token = True

    def add_packet_to_queue(self, packet: Packet):
        self.message_queue.append(packet)

    def send_packet(self, packet: Packet, add_error_chance: bool = False):
        # Log
        if isinstance(packet, DataPacket):
            self.logger.debug("Sending data packet")
        elif isinstance(packet, TokenPacket):
            self.logger.debug("Sending token")

        # Introduce error in transmission with error_probability chance
        if isinstance(packet, DataPacket) and random.random() < self.error_probability:
            if add_error_chance == True:
                packet.crc = packet.crc[:-1] + ('0' if packet.crc[-1] == '1' else '1') # alter the packet's crc
                packet.header = packet.create_header() # create the header with the altered crc
                self.logger.debug(f"Error introduced in the packet with destination: {packet.destination_name}")

        # Send the packet with a socket
        self.socket.sendto(packet.header.encode(), (self.ip, self.port)) 

        # Log
        if isinstance(packet, DataPacket):
            self.logger.debug("Data packet sent.")
            self.logger.debug('-'*50+'\n')
        elif isinstance(packet, TokenPacket):
            self.logger.debug("Token sent.")
            self.logger.debug('-'*50+'\n')

    def receive_packet(self):
        data, _ = self.socket.recvfrom(1024) # receive the packet
        packet_type = Packet.get_packet_type(data.decode()) # get the packet type
        packet = TokenPacket() if packet_type == "1000" else DataPacket.create_header_from_string(data.decode()) # create the packet from the received header
        self.logger.debug("Packet received. Initiating processing...\n")
        return self.process_packet(packet) # process the packet

    @classmethod
    def create_machine_from_file(cls, file_path: str, local_ip: str = "127.0.0.1", local_port: int = 6000):
        with open(file_path, 'r') as file:
            ip_and_port, nickname, time_token, has_token_str = [file.readline().strip() for _ in range(4)]
            has_token = has_token_str.lower() == "true"
        return cls(ip_and_port, nickname, time_token, has_token, local_ip=local_ip, local_port=local_port)

    def close_socket(self):
        self.socket.close()

    def run(self):
        if self.has_token == True:
            if len(self.message_queue) > 0: 
                self.logger.debug(f"Holding the token for {self.time_token} seconds...")
                time.sleep(int(self.time_token))  
                self.logger.debug("Sending a message...")
                packet = self.message_queue[0] # get the first one from the queue
                self.send_packet(packet, add_error_chance=True) # send the packet
            else:
                self.logger.debug(f"No message to send, holding the token for {self.time_token} seconds...\n")
                self.logger.debug('-'*50+'\n')
                time.sleep(int(self.time_token))  
                self.send_packet(self.token) # send the token
                self.has_token = False

    def process_packet(self, packet: Packet):

        # Received a token
        if packet.id == "1000":
            self.last_token_time = datetime.datetime.now() # update the time of the last token
            self.logger.debug("Token received.")
            if not self.has_token:
                self.has_token = True
                self.token = packet
                self.run() # run the token-holding and message-sending process
            else:
                pass

        # Received a data packet
        elif packet.id == "2000":
            if packet.destination_name == self.nickname: # if the packet is for me
                self.logger.debug("@@@Packet@@@!")
                calculated_crc = packet.calculate_crc() # calculate crc
                if calculated_crc == packet.crc:
                    packet.error_control = "ACK" # change the state
                    self.logger.debug(f"Message received successfully! Content: {packet.message}")
                else:
                    packet.error_control = "NACK" # change the state
                    self.logger.debug(f"Error in the received message. Divergent CRC!")

                self.logger.debug("Sending packet back...\n")
                self.logger.debug('-'*50+'\n')
                packet.header = packet.create_header() # create the header
                self.send_packet(packet) # send it back

            elif packet.origin_name == self.nickname: # if the packet was sent by me and is coming back
                self.logger.debug("@@@Packet back@@@")
                self.logger.debug(f"Message contained in the packet: {packet.message}\n")
                
                if packet.error_control == "ACK": # if the message was received successfully
                    self.logger.debug(f"Message sent was received by the destination!")
                    self.message_queue.pop(0) # remove it from the queue
                    self.logger.debug("Packet removed from the queue")
                    self.logger.debug("@@@Passing the token@@@")
                    self.send_packet(self.token) # send the token
                    self.has_token = False # no longer have the token

                elif packet.error_control == "NACK": # if there was an error in the message
                    self.logger.debug("An error occurred in the message")
                    self.send_packet(packet) # resend the packet if there was an error

                elif packet.error_control == "maquinanaoexiste": # if the machine doesn't exist
                    self.logger.debug("Machine was not found on the network.")
                    self.message_queue.pop(0) # remove it from the queue
                    self.logger.debug("Sending the token...")
                    self.send_packet(self.token) # send the token
                    self.has_token = False # no longer have the token

            elif packet.destination_name == "BROADCAST": # if the packet is for everyone
                self.logger.debug("Packet for everyone!")

                if packet.origin_name == self.nickname: # if the packet was sent by me to everyone and is coming back
                    self.logger.debug("Packet back!")
                    self.logger.debug(f"Message contained in the packet: {packet.message}\n")
                    self.logger.debug("Packet removed from the queue")
                    self.logger.debug("Passing the token...")
                    self.message_queue.pop(0) # remove it from the queue
                    self.send_packet(self.token) # send the token
                    self.has_token = False # no longer have the token

                else:
                    calculated_crc = packet.calculate_crc() # calculate crc
                    if calculated_crc == packet.crc:
                        self.logger.debug(f"Message received successfully! Content: {packet.message}")
                        packet.error_control = "ACK" # change the state
                    else:
                        self.logger.debug(f"Error in the received message. Divergent CRC!")
                        packet.error_control = "NACK" # change the state

                self.logger.debug("Sending the packet back...\n")
                self.logger.debug('-'*50+'\n')
                packet.header = packet.create_header() # create the header
                self.send_packet(packet) # send it back

            else:
                self.send_packet(packet) # pass it on to the next

    def check_token_status(self):
        while not self.terminate_event.is_set():  # Check for the terminate_event here
            time.sleep(int(self.time_token))

            if self.last_token_time is None:
                continue

            time_since_last_token = (datetime.datetime.now() - self.last_token_time).total_seconds()

            
            if time_since_last_token > self.TIMEOUT_VALUE:  # TIMEOUT_VALUE é o tempo máximo permitido sem ver o token
                
                self.logger.debug('\n'+'-'*50+'\n')
                self.logger.debug(f"Token não visto por muito tempo. Gerando novo token.")
                self.logger.debug('\n'+'-'*50+'\n')
                
                self.generate_token()
                self.last_token_time = datetime.datetime.now()
                pass

            elif time_since_last_token < self.MINIMUM_TIME:  # MINIMUM_TIME é o tempo mínimo esperado entre as passagens do token
                
                self.logger.debug('\n'+'-'*50+'\n')
                self.logger.debug(f"Token visto muito rapidamente. Retirando token da rede.")
                self.logger.debug('\n'+'-'*50+'\n')
                
                self.has_token = False
                pass



    def listen_for_packets(self):
    
        while not self.terminate_event.is_set():
            try:
                self.receive_packet()
            except Exception as e:
                self.logger.debug(f"Erro ao receber packet: {e}")

            
            
    def stop_listening(self):
        
        # Join the listening thread
        try:
            self.listen_thread.join(timeout=5)
        except Exception as e:
            self.logger.debug(f"Error joining listen_thread: {e}")

        # If there's a token checker thread, join it too
        if self.controls_token:
            try:
                self.token_checker_thread.join(timeout=5)
            except Exception as e:
                self.logger.debug(f"Error joining token_checker_thread: {e}")

        # Close the socket
        self.close_socket()



    def user_interaction(self):
        
        while not self.terminate_event.is_set():
            print("\nOptions:")
            print("1. Add a new packet to the queue")
            print("2. Turn off the machine")
            print("3. Show the current message queue")
            choice = input("Enter your choice:  ")

            if choice == "1":
                print("What type of packet do you want to send? Enter token [A] or data [B].")
                tipo = input("Enter the packet type: ")
                if tipo == "B":
                    destination_name = input("Enter the destination name: ")
                    message = input("Enter the message: ")
                    new_packet = DataPacket(origin_name=self.nickname, destination_name=destination_name, error_control="maquinanaoexiste", message=message)
                    print(f"Packet added to the queue for {destination_name} with the message: {message}")
                elif tipo == "A":
                    new_packet = TokenPacket()
                    print(f"Token added to the queue.")
                else:
                    print("Invalid packet type. Please try again.")
                
                self.add_packet_to_queue(new_packet)

            elif choice == "2":
                print("Turning off the machine")
                self.terminate_event.set()
                self.stop_listening()
                print("Machine shutdown complete.")
                sys.exit(0)

            elif choice == "3":
                print("Fila de mensagens atual:")
                for packet in self.message_queue:
                    print(packet.message) 

            else:
                print("Invalid choice. Please try again.")
