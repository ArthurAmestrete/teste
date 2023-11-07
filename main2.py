from src.network.data_packet import DataPacket
from src.network.machine import Machine

# pkg1 = DataPacket(origin_name="Host2", destination_name="Host1", 
#                   error_control="maquinanaoexiste", message="Teste D")

# pkg2 = DataPacket(origin_name="Host2", destination_name="Host1", 
#                   error_control="maquinanaoexiste", message="Teste E")

# pkg3 = DataPacket(origin_name="Host2", destination_name="Host1", 
#                   error_control="maquinanaoexiste", message="Teste F")

host2 = Machine.create_machine_from_file("machine_files/Host2.txt", local_port=6001, local_ip="127.0.0.1")
# host2.add_packet_to_queue(pkg1)
# host2.add_packet_to_queue(pkg2)
# host2.add_packet_to_queue(pkg3)
host2.start()