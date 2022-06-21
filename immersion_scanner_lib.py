import math
from operator import concat
import time
from tracemalloc import start
from matplotlib import pyplot as plt
import numpy as np
import pyvisa
from enum import Enum
import paho.mqtt.client as mqtt
from matplotlib.patches import Circle
import mpl_toolkits.mplot3d.art3d as art3d



class connection_types(Enum):
    visa = 1
    mqtt = 2

class immersion_scanner:

    __visa_instrument = None
    __mqtt_client = None
    __write_topic = "arduino/commands"
    __read_topic = "arduino/prints"
    buffer = []

    resource_manager = pyvisa.ResourceManager("@py")
    int_per_grame_calibration = -12.72
    water_grames_per_cubic_meter = 1000000
    cubic_meter_calibration = int_per_grame_calibration * water_grames_per_cubic_meter
    steps_per_m = 200/0.00125

    def __init__(self, connection_type, resource_name="Not Visa", mqtt_brocker="not mqtt", mqtt_brocker_port=1883):
        if (connection_type == connection_types.visa):
            self.__start_visa_instrument(resource_name)
        elif (connection_type == connection_types.mqtt):
            self.__start_mqtt_instrument(mqtt_brocker, mqtt_brocker_port)

    
    def __del__(self):
        self.end_instrument()


    def end_instrument(self):
        self.__end_visa_instrument()


    def send_command(self, command):
        self.__send_visa_command(command)


    def read_to_buffer(self, command=""):
        return True


    def read_command(self):
        return self.__read_visa_command()


    def query_command(self, command):
        return self.__query_visa_command(command)
    

    def move_to(self, absolute_position, expected_move_time=2):
       self.send_command("OUTP:MOVE " + str(int(absolute_position))) 
       time.sleep(expected_move_time)

    
    def set_axis_home(self):
        self.send_command("CONT:CONF:AXIS:HOME")
        time.sleep(2)
    
    
    def set_auto_home(self):
        self.send_command("CONT:CONF:AXIS:AUHO")
        time.sleep(2)
    

    def set_motor_on(self):
        self.send_command("CONT:CONF:MOTR:ON")
        time.sleep(2)
    
    
    def set_motor_off(self):
        self.send_command("CONT:CONF:MOTR:OFF")
        time.sleep(10)

    
    def measure_buoyancy(self, averages=100):
        return float(self.query_command("MEAS:BUOY " + str(int(averages)))) / self.cubic_meter_calibration
    

    def measure_buoyancy_and_filter(self, averages=100):
        readings_list = []

        # self.read_to_buffer("MEAS:BUOY:VALS " + str(int(averages)))
        reading = (self.query_command("MEAS:BUOY:VALS " + str(int(averages))))
        readings_list = reading.split(",")
        readings_list.pop()
        for i in range(len(readings_list)):
            readings_list[i] = int(readings_list[i]) / self.cubic_meter_calibration

        farless_list = self.filter_measures(readings_list, 400 / abs(self.cubic_meter_calibration))
        farless_list = self.filter_measures(farless_list, 70 / abs(self.cubic_meter_calibration))
        farless_list = self.filter_measures(farless_list, 40 / abs(self.cubic_meter_calibration))
        if (averages < 50 and len(farless_list) != 0):
            average = sum(farless_list)/len(farless_list)
        else:
            average = self.get_average_by_filtering_by_deviation(farless_list)

        if (average != None):
            return readings_list, farless_list, average
        else:
            print("repeating")
            return self.measure_buoyancy_and_filter(averages)

    
    def get_average_by_filtering_by_deviation(self, measures):
        accepted_standard_deviation = 25 / abs(self.cubic_meter_calibration)
        groups_size = 50
        average_acum = 0
        considered_groups = 0
        for i in range(len(measures) // groups_size):
            group = measures[i * groups_size:(i + 1) * groups_size]
            standard_deviation = np.std(np.array(group))

            if (standard_deviation < accepted_standard_deviation):
                considered_groups += 1
                average_acum += sum(group) / len(group)
        if (considered_groups == 0):
            return None
        else:
            return average_acum / considered_groups

    def filter_measures(self, readings_list, accepted_deviation=100):
        if (len(readings_list) == 0):
            return []
        average = sum(readings_list) / len(readings_list)
        farless_list = []
        for reading in readings_list:
            if (abs(reading - average) < accepted_deviation):
                farless_list.append(reading)
        return farless_list
    

    def scann_object(self, layer_height, layer_count, averages):
        layer_height_steps = layer_height * self.steps_per_m
        measures = []
        heights = []
        self.set_motor_on()
        self.move_to(0)
        self.set_axis_home()
        for i in range(layer_count + 1):
            self.set_motor_on()
            self.move_to(i * -layer_height_steps)
            self.set_motor_off()
            measures1, measures2, average_new = self.measure_buoyancy_and_filter(averages)
            print(average_new)
            measures.append(average_new)
            heights.append(i * layer_height_steps)
        layer_volumes = []
        for i in range(1, len(measures)):
            layer_volumes.append(measures[i] - measures[i - 1])
        heights_m = [i / self.steps_per_m for i in heights[0:len(heights) - 1]]
        return (layer_volumes, heights_m)
    

    @staticmethod
    def plot_scaned_object(measures, heights):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        radiuses = [math.sqrt(abs(measure / ((heights[1] - heights[0]) * math.pi))) for measure in measures]
        for radius, height in zip(radiuses, heights):
            Xc,Yc,Zc = immersion_scanner.__get_cilinder_plot_data(height, radius, abs(heights[1] - heights[0]))
            ax.plot_surface(Xc, Yc, Zc, alpha=0.5)

        plt.show()
    
    @staticmethod
    def plot_scaned_object_2(radiuses, heights):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for radius, height in zip(radiuses, heights):
            Xc,Yc,Zc = immersion_scanner.__get_cilinder_plot_data(height, radius, abs(heights[1] - heights[0]))
            ax.plot_surface(Xc, Yc, Zc, alpha=0.5)

        plt.show()
    

    @staticmethod
    def get_plot_data_from_measures(measures, heights):
        radiuses = [math.sqrt(abs(measure / ((heights[1] - heights[0]) * math.pi))) for measure in measures]
        surfaces = []
        print("radiuses")
        print(radiuses)
        print("heights")
        print(heights)
        for radius, height in zip(radiuses, heights):
            Xc,Yc, Zc = immersion_scanner.__get_cilinder_plot_data(height, radius, abs(heights[1] - heights[0]))
            surfaces.append((Xc, Yc, Zc))
        return surfaces
    
    
    @staticmethod
    def add_subplot_to_fig_from_measures(fig, measures, heights):
        ax = fig.add_subplot(111, projection="3d")
        surfaces = immersion_scanner.get_plot_data_from_measures(measures, heights)
        layer_height = abs(heights[1] - heights[0])
        for (Xc, Yc, Zc), height in zip(surfaces, heights):
            alpha_val = 0.5
            color_val = "red"
            ax.plot_surface(Xc, Yc, Zc, alpha=alpha_val, color=color_val)
            p = Circle((0, 0), Xc[0][0], alpha=alpha_val, color=color_val)
            ax.add_patch(p)
            art3d.pathpatch_2d_to_3d(p, z=height, zdir="z")
            p = Circle((0, 0), Xc[0][0], alpha=alpha_val, color=color_val)
            ax.add_patch(p)
            art3d.pathpatch_2d_to_3d(p, z=(height + layer_height), zdir="z")
        return ax


    def get_id(self):
        return self.query_command("*IDN?")


    def __start_visa_instrument(self, resource_name):
        self.__visa_instrument = self.resource_manager.open_resource(resource_name)
        self.__visa_instrument.timeout = None

        self.query_command = self.__query_visa_command
        self.send_command = self.__send_visa_command
        self.read_command = self.__read_visa_command
        self.end_instrument = self.__end_visa_instrument
        self.read_to_buffer = self.__read_visa_to_buffer

        while not self.read_command().startswith("Instrument setup"):
            print("Waiting for instrument setup...")
            time.sleep(1)
        print("Instrument setup complete")

    
    def __start_mqtt_instrument(self, mqtt_brocker, mqtt_brocker_port):
        self.__mqtt_client = mqtt.Client("vscode")
        self.__mqtt_client.connect(mqtt_brocker, mqtt_brocker_port) 
        self.__mqtt_client.loop_start()
        self.__mqtt_client.subscribe(self.__read_topic)
        self.__mqtt_client.on_message = self.__on_mqtt_message

        self.end_instrument = self.__end_mqtt_instrument
        self.query_command = self.__query_mqtt_command
        self.send_command = self.__send_mqtt_command
        self.read_command = self.__read_mqtt_command
        self.read_to_buffer = self.__read_mqtt_to_buffer


    def __read_visa_to_buffer(self, command):
        if (command != ""):
            self.send_command(command)

        self.buffer = []
        current_reading = self.__read_visa_command()
        while current_reading != "":
            self.buffer.append(current_reading[:-2])
            time.sleep(0.5)
            current_reading = self.__read_visa_command()
        if (self.buffer[-1] == ""):
            self.buffer.pop()
            return True
        else:
            return False


    def __read_mqtt_to_buffer(self, command=""):
        self.buffer = []

        self.__mqtt_client.on_message = self.__on_mqtt_message_to_buffer

        if (command != ""):
            self.send_command(command)

        start_time = time.time()
        while (len(self.buffer) == 0 and (time.time() - start_time) < 2):
            pass

        if (len(self.buffer) == 0):
            return False

        start_time = time.time()
        while (self.buffer[-1] != "" and (time.time() - start_time) < 30):
            pass

        self.__mqtt_client.on_message = self.__on_mqtt_message

        if (self.buffer[-1] == ""):
            self.buffer.pop()
            return True
        else:
            return False


    def __end_mqtt_instrument(self):
        return


    def __end_visa_instrument(self):
        if (self.__visa_instrument == None):
            raise ValueError("Visa instrument method used in a non visa scanner. __visa_instrument was None")
        
        self.__visa_instrument.close()
    

    def __query_visa_command(self, command):
        if (self.__visa_instrument == None):
            raise ValueError("Visa instrument method used in a non visa scanner. __visa_instrument was None")
        if (command.startswith("MEAS:BUOY:VALS ")):
            return self.__visa_instrument.query(command)
        self.__visa_instrument.timeout = 5000
        try:
            printString = self.__visa_instrument.query(command)
            self.__visa_instrument.timeout = None
        except:
            printString = ""
            self.__visa_instrument.timeout = None
        return printString
        
    

    __return_mqtt_string = None

    def __on_mqtt_message(self, client, userdata, message):
        self.__return_mqtt_string = str(message.payload.decode("utf-8"))

    
    def __on_mqtt_message_to_buffer(self, client, userdata, message):
        self.buffer.append(str(message.payload.decode("utf-8")))


    def __query_mqtt_command(self, command):
        self.__mqtt_client.publish(self.__write_topic, command)
        self.__return_mqtt_string = None
        start_time = time.time()
        while (time.time() - start_time < 5):
            if (self.__return_mqtt_string != None):
                return (self.__return_mqtt_string)
        return ("")
    

    def __send_visa_command(self, command):
        if (self.__visa_instrument == None):
            raise ValueError("Visa instrument method used in a non visa scanner. __visa_instrument was None")
        
        self.__visa_instrument.write(command)
        time.sleep(0.5)

    
    def __send_mqtt_command(self, command):
        self.__mqtt_client.publish(self.__write_topic, command)




    def __read_visa_command(self):
        if (self.__visa_instrument == None):
            raise ValueError("Visa instrument method used in a non visa scanner. __visa_instrument was None")
        
        self.__visa_instrument.timeout = 5000
        try:
            reading = self.__visa_instrument.read() 
            self.__visa_instrument.timeout = None
            return reading

        except:
            self.__visa_instrument.timeout = None
            return ""


    def __read_mqtt_command(self):
        start_time = time.time()
        prev_return_mqtt_string = self.__return_mqtt_string
        while (prev_return_mqtt_string == self.__return_mqtt_string):
            if (time.time() - start_time > 5):
                return ("")
        return self.__return_mqtt_string


    @staticmethod
    def __get_cilinder_plot_data(center_z, radius, height):
        z = np.linspace(center_z, center_z + height, 2)
        theta = np.linspace(0, 2*np.pi, 50)
        theta_grid, z_grid=np.meshgrid(theta, z)
        x_grid = radius*np.cos(theta_grid)
        y_grid = radius*np.sin(theta_grid)
        return x_grid,y_grid,z_grid

