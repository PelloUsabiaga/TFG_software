import math
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import StringVar, ttk
from tkinter.messagebox import showinfo
from xmlrpc.server import SimpleXMLRPCRequestHandler
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.style import available
import numpy as np
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.patches import Circle
from pyparsing import col
from immersion_scanner_lib import immersion_scanner, connection_types
import pyvisa
import mpl_toolkits.mplot3d.art3d as art3d


class scanner_window:

    scanner = None

    def __init__(self):
        self.current_scanned_object_data = None
        self.showing_wait_window = False

        self.root = tk.Tk()
        self.root.title("3D scanner")

        window_width = 1200
        window_height = 700

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        center_x = int(screen_width/2 - window_width / 2)
        center_y = int(screen_height/2 - window_height / 2)

        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        self.root.resizable(True, True)
        # self.root.iconbitmap("sources/logo_upv_ehu.ico")


        self.selection_frame = tk.Frame(self.root)
        self.selection_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        self.selection_frame['borderwidth'] = 3
        self.selection_frame['relief'] = 'groove'
        self.selection_frame.columnconfigure(0, weight=1)
        self.selection_frame.columnconfigure(1, weight=1)

        ttk.Label(self.selection_frame, text="VISA", font=("Arial", 25)).grid(column=0, row=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(self.selection_frame, text="MQTT", font=("Arial", 25)).grid(column=1, row=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(self.selection_frame, text="Search and select your Visa instrument:").grid(column=0, row=1, sticky=tk.W, padx=10, pady=3)
        self.visa_search_button = ttk.Button(self.selection_frame, text='Search for aviable instruments',command=self.get_aviable_instruments)
        self.visa_search_button.grid(column=0, row=1, sticky=tk.E, padx=10, pady=3)

        self.selected_visa_instrument = tk.StringVar()
        self.aviable_visa_instruments_combobox = ttk.Combobox(self.selection_frame, textvariable=self.selected_visa_instrument)
        self.aviable_visa_instruments_combobox.grid(column=0, row=2, sticky=tk.W + tk.E, padx=10, pady=3, )

        ttk.Label(self.selection_frame, text="Type your mqtt server URL or IP:").grid(column=1, row=1, sticky=tk.W, padx=10, pady=3)
        self.mqtt_server = tk.StringVar()
        self.mqtt_server_entry = ttk.Entry(self.selection_frame, textvariable=self.mqtt_server)
        self.mqtt_server_entry.grid(column=1, row=2, sticky=tk.W, padx=10, pady=3)
        self.mqtt_server_entry.insert(0, "192.168.2.47")
        ttk.Label(self.selection_frame, text="Type the mqtt server port:").grid(column=1, row=3, sticky=tk.W, padx=10, pady=3)
        self.mqtt_port = tk.StringVar()
        self.mqtt_port_entry = ttk.Entry(self.selection_frame, textvariable=self.mqtt_port)
        self.mqtt_port_entry.grid(column=1, row=4, sticky=tk.W, padx=10, pady=3)
        
        self.create_scanner_button = ttk.Button(self.selection_frame, text="Create scanner", command=self.create_scanner)
        self.create_scanner_button.grid(column=1, row=5, sticky=tk.E, padx=10, pady=3, ipadx=10, ipady=3)


        self.instrument_frame = tk.Frame(self.root, background="light grey")
        self.instrument_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        self.instrument_frame['borderwidth'] = 3
        self.instrument_frame['relief'] = 'groove'

        self.instrument_frame.columnconfigure(0, weight=1)
        self.instrument_frame.columnconfigure(1, weight=1)

        self.command_frame_buttons = []
        self.commands_frame = tk.Frame(self.instrument_frame, background="light grey")
        self.commands_frame.columnconfigure(0, weight=1)
        self.commands_frame.grid(column=0, row=0, sticky="nsew")

        self.command_in_entry = tk.StringVar()
        self.command_entry = ttk.Entry(self.commands_frame, textvariable=self.command_in_entry)
        self.command_entry.grid(column=0, row=0, sticky="ew", ipadx=5, ipady=5)

        self.command_send_button = ttk.Button(self.commands_frame, text="Send", command=self.send_command)
        self.command_send_button.grid(column=0, row=0, sticky=tk.E)
        self.command_frame_buttons.append(self.command_send_button)

        self.scrolled_bar = tk.Frame(self.commands_frame)
        self.scrolled_bar.grid(column=0, row=1, sticky="nsew")
        self.scrolled_bar.columnconfigure(0, weight=1)

        self.console = tk.Text(self.scrolled_bar, state='disabled', height=25)
        self.console.grid(column=0, row=1, sticky="ew")

        scrollbar = ttk.Scrollbar(self.scrolled_bar, orient='vertical', command=self.console.yview)
        scrollbar.grid(column=1, row=1, sticky="ns")

        self.console['yscrollcommand'] = scrollbar.set

        self.command_buttons = tk.Frame(self.commands_frame)
        self.command_buttons.grid(column=0, row=2, sticky="nsew")
        self.command_buttons.columnconfigure(0, weight=1)
        self.command_buttons.columnconfigure(1, weight=1)
        self.command_buttons.columnconfigure(2, weight=1)

        self.motor_on_button = ttk.Button(self.command_buttons, text="Motor ON", command=self.motor_on_button_clicked)
        self.motor_on_button.grid(column=0, row=0, sticky="nsew")
        self.command_frame_buttons.append(self.motor_on_button)
        
        self.motor_off_button = ttk.Button(self.command_buttons, text="Motor OFF", command=self.motor_off_button_clicked)
        self.motor_off_button.grid(column=0, row=1, sticky="nsew")
        self.command_frame_buttons.append(self.motor_off_button)

        self.set_axis_home_button = ttk.Button(self.command_buttons, text="Set axis home", command=self.set_axis_home_button_clicked)
        self.set_axis_home_button.grid(column=1, row=0, sticky="nsew")
        self.command_frame_buttons.append(self.set_axis_home_button)
        
        self.test_button = ttk.Button(self.command_buttons, text="test", command=self.test_button_clicked)
        self.test_button.grid(column=2, row=0, sticky="nsew")
        self.command_frame_buttons.append(self.test_button)
        
        self.get_measures_button = ttk.Button(self.command_buttons, text="Get measures", command=self.test_button_clicked)
        self.get_measures_button.grid(column=2, row=1, sticky="nsew")
        self.command_frame_buttons.append(self.get_measures_button)

        self.download_button = ttk.Button(self.command_buttons, text="Download measures", command=self.download_button_clicked)
        self.download_button.grid(column=1, row=1, sticky="nsew")
        self.command_frame_buttons.append(self.download_button)



        self.view_frame = tk.Frame(self.instrument_frame, background="blue")
        self.view_frame.grid(column=1, row=0, sticky="nsew")
        self.view_frame.columnconfigure(0, weight=1)     

        self.view_frame.columnconfigure(0, weight=1)

        self.scann_buttons_frame = tk.Frame(self.view_frame)
        self.scann_buttons_frame.grid(column=0, row=0, sticky="nsew")
        self.scann_buttons_frame.columnconfigure(0, weight=1)
        self.scann_buttons_frame.columnconfigure(1, weight=1)


        ttk.Label(self.scann_buttons_frame, text="Layer height").grid(column=0, row=0, sticky=tk.W, padx=10, pady=3)
        self.layer_height = tk.StringVar()
        self.layer_height_entry = ttk.Entry(self.scann_buttons_frame, textvariable=self.layer_height)
        self.layer_height_entry.grid(column=0, row=1, sticky=tk.W, padx=10, pady=3)
        self.layer_height_entry.insert(0, "0.05")

        ttk.Label(self.scann_buttons_frame, text="Layers number").grid(column=1, row=0, sticky=tk.W, padx=10, pady=3)
        self.layers_number = tk.StringVar()
        self.layers_number_entry = ttk.Entry(self.scann_buttons_frame, textvariable=self.layers_number)
        self.layers_number_entry.grid(column=1, row=1, sticky=tk.W, padx=10, pady=3)
        self.layers_number_entry.insert(0, "5")

        ttk.Label(self.scann_buttons_frame, text="Averagues").grid(column=2, row=0, sticky=tk.W, padx=10, pady=3)
        self.averagues = tk.StringVar()
        self.averagues_entry = ttk.Entry(self.scann_buttons_frame, textvariable=self.averagues)
        self.averagues_entry.grid(column=2, row=1, sticky=tk.W, padx=10, pady=3)
        self.averagues_entry.insert(0, "100")

        self.scann_figure_button = ttk.Button(self.scann_buttons_frame, text="Scann figure", command=self.scann_figure)
        self.scann_figure_button.grid(column=0, row=2, sticky="nsew")
        self.command_frame_buttons.append(self.scann_figure_button)

        self.update_figure_button = ttk.Button(self.scann_buttons_frame, text="Update figure", command=self.update_figure)
        self.update_figure_button.grid(column=2, row=2, sticky="nsew")
        self.command_frame_buttons.append(self.update_figure_button)

        self.figure_frame = tk.Frame(self.view_frame)
        self.figure_frame.grid(column=0, row=1, sticky="nsew")

        self.ploted_figure = Figure(dpi=100)

        self.canvas = FigureCanvasTkAgg(self.ploted_figure, master=self.figure_frame)
        self.canvas.draw()

        measures = [9,7,200]
        heights = [1,2,3]

        self.sublplot = immersion_scanner.add_subplot_to_fig_from_measures(self.ploted_figure, measures, heights)


        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        for button in self.command_frame_buttons:
            button['state'] = tk.DISABLED

        self.root.mainloop()


    def disable_buttons(self):
        for button in self.command_frame_buttons:
            button['state'] = tk.DISABLED

    def enable_buttons(self):
        for button in self.command_frame_buttons:
            button['state'] = tk.NORMAL

    def update_figure(self):
        if (self.current_scanned_object_data == None):
            showinfo(title="Warning", message="No data for any scanned object. Please, scann some object.")
            return
        self.sublplot.clear()
        immersion_scanner.add_subplot_to_fig_from_measures(self.ploted_figure, self.current_scanned_object_data[0], self.current_scanned_object_data[1])
        self.canvas.draw_idle()

    def send_command(self):
        self.busy()
        self.root.update()
        text_to_print = self.scanner.query_command(self.command_in_entry.get())

        self.console.configure(state='normal')
        self.console.insert("end", text_to_print)
        self.console.configure(state='disabled')
        self.notbusy()
    
    def scann_figure(self):
        self.busy()
        self.root.update()
        try:
            lh = float(self.layer_height.get())
            lc = int(self.layers_number.get())
            av = int(self.averagues.get())        
        except Exception as e:
            showinfo(title="Error", message="Check ")
            print(e)
            return
        self.current_scanned_object_data = self.scanner.scann_object(lh, lc, av)
        self.notbusy()

    def download_button_clicked(self):
        measures = self.current_scanned_object_data[0]
        heights = self.current_scanned_object_data[0]
        radiuses = [math.sqrt(abs(measure / ((heights[1] - heights[0]) * math.pi))) for measure in measures]
        with open(Path.home() +"/Downloads/measures_" + str(time.time), 'w') as file:
            file.write(str(radiuses))
            file.write("\n")
            file.write(str(heights))
            file.write("\n")

    def test_button_clicked(self):
        self.scanner.measure_buoyancy_and_filter(1000)
    
    def busy(self):
        self.root.call("tk","busy","hold", self.root)
        self.disable_buttons()

    def notbusy(self):
        self.root.call("tk","busy","forget", self.root)
        self.enable_buttons()

    def motor_off_button_clicked(self):
        self.busy()
        self.root.update()
        self.scanner.set_motor_off()
        self.notbusy()
    
    def motor_on_button_clicked(self):
        self.busy()
        self.root.update()
        self.scanner.set_motor_on()
        self.notbusy()

    def set_axis_home_button_clicked(self):
        self.scanner.set_axis_home()
    
    def get_aviable_instruments(self):
        rm = pyvisa.ResourceManager("@py")
        self.aviable_visa_instruments_combobox["values"] = rm.list_resources()
    
    def create_scanner(self):
        self.busy()
        self.root.update()
        if (self.selected_visa_instrument.get() != "" and self.mqtt_server.get() != ""):
            showinfo(title="Warning", message="Select only a visa instrument or a mqtt connection")
            return
        if (self.selected_visa_instrument.get() != ""):
            try:
                self.scanner = immersion_scanner(connection_types.visa, resource_name=self.selected_visa_instrument.get())
            except Exception as e:
                showinfo(title="Error", message="Selected visa instrument could not be created")
                print(e)
                return
        elif (self.mqtt_server.get() != ""):
            try:
                if (self.mqtt_port.get() != ""):
                    self.scanner = immersion_scanner(connection_types.mqtt, mqtt_brocker=self.mqtt_server.get(), mqtt_brocker_port=self.mqtt_port.get())
                else:
                    self.scanner = immersion_scanner(connection_types.mqtt, mqtt_brocker=self.mqtt_server.get())
            except Exception as e:
                showinfo(title="Error", message="Selected mqtt instrument could not be created")
                print(e)
                return
        else:
            showinfo(title="Warning", message="Please, select some instrument from the list, or configure a mqtt connection")
            return
        
        for button in self.command_frame_buttons:
            button['state'] = tk.NORMAL
        self.notbusy()


if __name__ == "__main__":
    application_window = scanner_window()

