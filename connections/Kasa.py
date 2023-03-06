import json
import struct
from builtins import bytes


# adapted from https://github.com/p-doyle/Python-KasaSmartPowerStrip/tree/CircuitPython had to used different socket lib
# add concurrency method to turn off after delay incase program crashes so pump doesn't run out of water and keep going

# these 2 libraries are specific to Circuit Python
#from socketpool import SocketPool
#import wifi

from connections.secrets import secrets  # pylint: disable=no-name-in-module
import board
import busio
from digitalio import DigitalInOut
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_esp32spi.adafruit_esp32spi_socket as socket

spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
esp32_cs = DigitalInOut(board.CS1)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)
esp.connect(secrets)




class SmartPowerStrip(object):

    def __init__(self, ip, device_id=None, timeout=2.0, protocol='tcp'):
        self.ip = ip
        self.port = 9999
        self.protocol = protocol
        self.device_id = device_id
        self.sys_info = None
        self.timeout = timeout

        # create a socket pool using the wifi radio
        #self.socket_pool = SocketPool(wifi.radio)

        self.sys_info = self.get_system_info()['system']['get_sysinfo']

        if not self.device_id:
            self.device_id = self.sys_info['deviceId']

        
        

    def set_wifi_credentials(self, ssid, psk, key_type='3'):
        '''
        :param ssid: router ssid
        :param psk: router passkey
        :param key_type: 3 is WPA2, 2 might be WPA and 1 might be WEP?
        :return: command response
        '''

        wifi_command = '{"netif":{"set_stainfo":{"ssid":"' + ssid + '","password":"' + \
                       psk + '","key_type":' + key_type + '}}}'

        return self.send_command(wifi_command, self.protocol)

    def set_cloud_server_url(self, server_url=''):

        server_command = '{"cnCloud":{"set_server_url":{"server":"' + server_url + '"}}}'

        return self.send_command(server_command, self.protocol)

    def get_system_info(self):

        return self._udp_send_command('{"system":{"get_sysinfo":{}}}')

    def get_realtime_energy_info(self, plug_num=None, plug_name=None):

        plug_id = self._get_plug_id(plug_num=plug_num, plug_name=plug_name)

        energy_command = '{"context":{"child_ids":["' + plug_id + '"]},"emeter":{"get_realtime":{}}}'

        response = self.send_command(energy_command, self.protocol)

        realtime_energy_data = response['emeter']['get_realtime']

        return realtime_energy_data

    def get_historical_energy_info(self, month, year, plug_num=None, plug_name=None):

        plug_id = self._get_plug_id(plug_num=plug_num, plug_name=plug_name)

        energy_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
                         '"emeter":{"get_daystat":{"month": ' + month + ',"year":' + year + '}}}'

        response = self.send_command(energy_command, self.protocol)

        historical_energy_data = response['emeter']['get_daystat']['day_list']

        return historical_energy_data

    def toggle_relay_leds(self, state):

        state_int = self._get_plug_state_int(state, reverse=True)

        led_command = '{"system":{"set_led_off":{"off":' + str(state_int) + '}}}'

        return self.send_command(led_command, self.protocol)

    def set_plug_name(self, plug_num, plug_name):

        plug_id = self._get_plug_id(plug_num=plug_num)

        set_name_command = '{"context":{"child_ids":["' + plug_id + \
                           '"]},"system":{"set_dev_alias":{"alias":"' + plug_name + '"}}}'

        return self.send_command(set_name_command, self.protocol)

    def get_plug_info(self, plug_num):

        # WARNING: circuit python does not support str.zfill so manually padding the plug id #
        target_plug = [plug for plug in self.sys_info['children'] if plug['id'] == '0' + str(int(plug_num)-1)]

        return target_plug

    # toggle multiple plugs by id or name
    def toggle_plugs(self, state, plug_num_list=None, plug_name_list=None):

        state_int = self._get_plug_state_int(state)

        plug_id_list_str = self._get_plug_id_list_str(plug_num_list=plug_num_list, plug_name_list=plug_name_list)

        all_relay_command = '{"context":{"child_ids":' + plug_id_list_str + '},' + \
                            '"system":{"set_relay_state":{"state":' + str(state_int) + '}}}'

        return self.send_command(all_relay_command, self.protocol)

    # toggle a single plug
    def toggle_plug(self, state, plug_num=None, plug_name=None):

        state_int = self._get_plug_state_int(state)

        plug_id = self._get_plug_id(plug_num=plug_num, plug_name=plug_name)

        relay_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
                        '"system":{"set_relay_state":{"state":' + str(state_int) + '}}}'

        return self.send_command(relay_command, self.protocol)

    def reboot(self, delay=1):
        reboot_command = '{"system":{"reboot":{"delay":' + str(delay) + '}}}'
        return self.send_command(reboot_command, self.protocol)
    
    def timed_toggle(self, state, plug_num=None, plug_name=None, delay=5, retry=True):
        
        self.clear_safe(plug_num=plug_num, plug_name=plug_name)

        self.toggle_plug(state, plug_num, plug_name)

        plug_id = self._get_plug_id(plug_num=plug_num, plug_name=plug_name)

        relay_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
            '"count_down":{"add_rule":{"enable":1,"delay":'+ str(delay) +',"act":0,"name":"turn off"}}}'


        sent =self.send_command(relay_command, self.protocol)

        
        if not sent and retry:
            print("retrying command")
            self.timed_toggle(self, state, plug_num, plug_name, delay, False)
        elif not sent:
            print(f"{relay_command} failed plug turned off")
            self.toggle_plug('off', plug_num, plug_name)

        relay_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
            '"count_down":{"get_rules":null}}'
        
        self.send_command(relay_command)
        
        return

    def clear_safe(self, plug_num=None, plug_name=None, id=None):

        if id == None and plug_num == None and plug_name == None:
            relay_command = '{"count_down":{"delete_all_rules":null}}'
        
        elif plug_name != None or plug_num != None:
            plug_id = self._get_plug_id(plug_num=plug_num, plug_name=plug_name)
            
            if id == None:
                relay_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
                '"count_down":{"delete_all_rules":null}}'
            else:
                relay_command = '{"context":{"child_ids":["' + plug_id + '"]},' + \
                '"count_down":{"delete_rules":{"id":' + str(id) +'}}}'
        
        elif id != None:
            relay_command = '{"count_down":{"delete_rules":{"id":' + str(id) +'}}}'
        
        return self.send_command(relay_command)


    # manually send a command
    def send_command(self, command, protocol='tcp'):

        if protocol == 'tcp':
            try:
                print(self._tcp_send_command(command))
                return True
            except:
                print("Command not sent: "+ command)
                return False
        elif protocol == 'udp':
            try:
                print(self._udp_send_command(command))
                return True
            except:
                print("Command not sent: "+ command)
                return False
            
        else:
            raise ValueError("Protocol must be 'tcp' or 'udp'")

    def _get_plug_state_int(self, state, reverse=False):

        if state.lower() == 'on':
            if reverse:
                state_int = 0
            else:
                state_int = 1
        elif state.lower() == 'off':
            if reverse:
                state_int = 1
            else:
                state_int = 0
        else:
            raise ValueError("Invalid state, must be 'on' or 'off'")

        return state_int

    # create a string with a list of plug_ids that can be inserted directly into a command
    def _get_plug_id_list_str(self, plug_num_list=None, plug_name_list=None):

        plug_id_list = []

        if plug_num_list:
            for plug_num in plug_num_list:

                # add as str to remove the leading u
                plug_id_list.append(str(self._get_plug_id(plug_num=plug_num)))

        elif plug_name_list:

            for plug_name in plug_name_list:
                # add as str to remove the leading u
                plug_id_list.append(str(self._get_plug_id(plug_name=plug_name)))

        # convert to double quotes and turn the whole list into a string
        plug_id_list_str = str(plug_id_list).replace("'", '"')

        return plug_id_list_str

    # get the plug child_id to be used with commands
    def _get_plug_id(self, plug_num=None, plug_name=None):

        if plug_num and self.device_id:
            # WARNING: circuit python does not support str.zfill so manually padding the plug id #
            plug_id = self.device_id + '0' + str(plug_num-1)

        elif plug_name and self.sys_info:
            target_plug = [plug for plug in self.sys_info['children'] if plug['alias'] == plug_name]
            if target_plug:
                plug_id = self.device_id + target_plug[0]['id']
            else:
                raise ValueError('Unable to find plug with name ' + plug_name)
        else:
            raise ValueError('Unable to find plug.  Provide a valid plug_num or plug_name')

        return plug_id

    def _tcp_send_command(self, command):

        #sock_tcp = self.socket_pool.socket(self.socket_pool.AF_INET, self.socket_pool.SOCK_STREAM)
        #sock_tcp.settimeout(self.timeout)
        #sock_tcp.connect((self.ip, self.port))

        socket.set_interface(esp)
        socketaddr = socket.getaddrinfo(self.ip, self.port)[0][4]
        s = socket.socket()
        s.settimeout(self.timeout)

        s.connect(socketaddr)

        s.send(self._encrypt_command(command))

        #data_buffer = bytearray(2048)
        #data_size = sock_tcp.recv_into(data_buffer)

        data_buffer = bytearray(2048)
        data_size = s.recv_into(data_buffer)
        
        s.close()

        # the first 4 chars are the length of the command so can be excluded
        return json.loads(self._decrypt_command(data_buffer[4:data_size]))

    def _udp_send_command(self, command):

        #client_socket = self.socket_pool.socket(self.socket_pool.AF_INET, self.socket_pool.SOCK_DGRAM)
        #client_socket.settimeout(self.timeout)

        #addr = (self.ip, self.port)

        #client_socket.sendto(self._encrypt_command(command, prepend_length=False), addr)

        socket.set_interface(esp)
        socketaddr = socket.getaddrinfo(self.ip, self.port)[0][4]
        s = socket.socket(type=socket.SOCK_DGRAM)
        
        s.settimeout(self.timeout)

        s.connect(socketaddr, conntype=esp.UDP_MODE)

        s.send(self._encrypt_command(command, prepend_length=False))


        #data_buffer = bytearray(2048)
        #data_size, server = client_socket.recvfrom_into(data_buffer)

        data_buffer = bytearray(2048)
        data_size = s.recv_into(data_buffer)
        
        s.close()

        return json.loads(self._decrypt_command(data_buffer[:data_size]))

    @staticmethod
    def _encrypt_command(string, prepend_length=True):

        key = 171
        result = b''

        # when sending get_sysinfo using udp the length of the command is not needed but
        #  with all other commands using tcp it is
        if prepend_length:
            result = struct.pack(">I", len(string))

        for i in bytes(string.encode('latin-1')):
            a = key ^ i
            key = a
            result += bytes([a])
        return result

    @staticmethod
    def _decrypt_command(string):

        key = 171
        result = b''
        for i in bytes(string):
            a = key ^ i
            key = i
            result += bytes([a])
        return result.decode('latin-1')

    