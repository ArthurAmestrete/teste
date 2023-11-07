from src.network.data_packet import DataPacket
from src.network.machine import Machine

# pkg1 = DataPacket(origin_name="Host1", destination_name="Host 2", 
#                   error_control="maquinanaoexiste", message="Teste A")

# pkg2 = DataPacket(origin_name="Host1", destination_name="Host 2", 
#                   error_control="maquinanaoexiste", message="Teste B")

# pkg3 = DataPacket(origin_name="Host1", destination_name="Host 2", 
#                   error_control="maquinanaoexiste", message="Teste C")

host1 = Machine.create_machine_from_file("machine_files/Host1.txt", local_port=6000, local_ip="127.0.0.1")
# host1.add_packet_to_queue(pkg1)
# host1.add_packet_to_queue(pkg2)
# host1.add_packet_to_queue(pkg3)
host1.start()
