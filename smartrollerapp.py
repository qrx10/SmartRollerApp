import sys
import random
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QWidget, QFileDialog, QStackedWidget,QCheckBox,QHBoxLayout,QComboBox
from PyQt5.QtCore import QTimer
from PyQt5 import QtGui
import serial
import time
from threading import Thread
import sys
import serial.tools.list_ports
import tkinter as tk
from tkinter import messagebox
import math
import csv
import os
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

Channels = 113
Taxels = 28
NumRow = 7
NumCol = 7

# value that are going to change
dx = []  # 3d x value. does not change in our case
dy = []  # 3d y value. does not change in our case
current_dz = []
num = 0
dz = np.zeros(Channels)  # 3d z value. change relative to capacitance
pressure_vals = np.zeros(Taxels)

shear_vals_x = np.zeros(Taxels)
shear_vals_y = np.zeros(Taxels)
arrows = []

data = []
word = []
timestamp = 0

average = []

recording = False
flag_COM = True
portNum = ''


# **********************Global variables end***************************#


def serial_port_init(serialPort):     # Serial port initializationst
    ser = serial.Serial(
    port=serialPort,
    baudrate=500000,
    timeout = None,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
    )
    ser.isOpen()
    return ser


def thread1():
    global word, current_dz, timestamp
    while True:
        line = ser.readline()
        try:
            data = line.decode()
            word = data.split(",")
            index = 0
            timestamp = int(time.perf_counter() * 1000)
            if len(word) >= Channels + 1:
                for index in range(Channels):
                    try:
                        dz[index] = float(word[index])
                    except ValueError:
                        pass
                calcValues()  # Update pressure_vals based on the new dz values
        except UnicodeDecodeError:
            pass



class MainWindow(QMainWindow):
    global pressure_vals,shear_vals_x,shear_vals_y,dz, timestamp
    def __init__(self):
        super().__init__()

        # Create a central widget and a layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        self.setWindowTitle('Smart Roller App')
        icon_path = os.path.join(os.path.abspath(os.getcwd()), r'smartrollericon.png')
        print(icon_path)
        self.setWindowIcon(QtGui.QIcon(icon_path))

        # Create a stacked widget to manage different views
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # Create a PyqtGraph PlotWidget for the heatmap
        self.heatmap_widget = pg.PlotWidget(self)
        layout.addWidget(self.heatmap_widget)

        self.serial_plot_widget = SerialPlotWidget()

        # Create start and record buttons
        self.start_button = QPushButton("Start Animation", self)
        layout.addWidget(self.start_button)

        self.record_button = QPushButton("Record", self)
        layout.addWidget(self.record_button)

        self.browse_button = QPushButton("Browse", self)
        layout.addWidget(self.browse_button)

        self.serialplot_button = QPushButton("Serial Plot", self)
        layout.addWidget(self.serialplot_button)

        # Set up the heatmap plot
        self.img_item = pg.ImageItem()
        self.heatmap_widget.addItem(self.img_item)

        # Add the widgets to the stacked widget
        self.stacked_widget.addWidget(self.heatmap_widget)
        self.stacked_widget.addWidget(self.serial_plot_widget)

        # Initially, show the heatmap widget
        self.stacked_widget.setCurrentWidget(self.heatmap_widget)

        # Set up the data array for the heatmap
        self.data = np.asarray(pressure_vals)
        # print(self.data)
        if len(self.data) == Taxels:
            self.data = np.asarray(pressure_vals).reshape((4, 7))
        # print(len(self.data))
        # Set up the arrow item
        # self.arrow_item = pg.ArrowItem(tipAngle=80, baseAngle=5, tailWidth=10, pen='y', brush='b', pxMode=False)
        # self.heatmap_widget.addItem(self.arrow_item)

        self.update_heatmap_and_arrows()

        # Set up the timer to update the heatmap and arrows
        self.timer = QTimer(self)
        self.recordTimer = QTimer(self)
        self.timer.timeout.connect(self.update_data_and_arrows)
        self.interval = 10  # Update interval in milliseconds

        self.recordStatus = False
        self.csv_file_path = None
        self.serialplotStatus = False
        self.serial_plot_widget.hide()

        # Connect the button click event to start the timer
        self.start_button.clicked.connect(self.toggle_timer)
        self.record_button.clicked.connect(self.toggle_record)
        self.browse_button.clicked.connect(self.browse_directory)
        self.serialplot_button.clicked.connect(self.serialplot)

        self.logdata = []
        self.num_channels = Channels
        self.recordTimer.timeout.connect(self.start_recording_data)
        self.temp_timestamp = -1
        

    def update_heatmap_and_arrows(self):
        self.img_item.setImage(self.data, levels=(-400,100))

        # Randomly set arrow position within the heatmap
        num_arrows = Taxels  # Replace this with the actual number of arrows

        # Create ArrowItem objects if they don't exist
        if not hasattr(self, 'arrows') or len(self.arrows) != num_arrows:
            self.arrows = self.create_arrows(num_arrows)
        

        # Set the positions and angles for each arrow
        for i in range(num_arrows):
            row = i%NumRow+0.5
            col = i//NumCol+0.5
            arrow_item = self.arrows[i]
            xlen = -shear_vals_x[i]*70/400
            ylen = -shear_vals_y[i]*70/400
            length = math.sqrt(math.pow(xlen, 2) + math.pow(ylen, 2))
            if length < 20:
                tlen = 0
                hlen = length
            else:
                tlen = length - 20
                hlen = 20

            arrow_item.setPos(col, row)  # Set the position at the tail
            arrow_item.setStyle(angle= -math.degrees(math.atan2(ylen, xlen)),headLen = hlen, tailLen = tlen)

    def create_arrows(self, num_arrows):
    # Create a list to store ArrowItem objects
        arrows = []
        for _ in range(num_arrows):
            arrow_item = pg.ArrowItem(angle=0, tipAngle=20, baseAngle=180, headLen=30, tailLen=10, tailWidth=5, pen='w')
            arrows.append(arrow_item)
            self.heatmap_widget.addItem(arrow_item)  # Add the ArrowItem to the heatmap_widget
        return arrows

    def update_data_and_arrows(self):

        self.data = np.asarray(pressure_vals)
        
        if len(self.data) == Taxels:
            self.data = np.asarray(pressure_vals).reshape((4, 7))
            self.update_heatmap_and_arrows()
        self.update_heatmap_and_arrows()

    def toggle_timer(self):
        if not self.timer.isActive():
            self.start_button.setText("Stop Animation")
            self.timer.start(self.interval)
        else:
            self.start_button.setText("Start Animation")
            self.timer.stop()

    def toggle_record(self):
        if not self.recordStatus:
            if not self.csv_file_path:
                return
            
            self.record_button.setText("Stop Recording")
            self.recordStatus = True
            self.logdata.clear()
            self.recordTimer.start(10)

        else:
            self.record_button.setText("Record")
            self.recordStatus = False
            if self.logdata:
                self.save_data_to_csv()

            self.recordTimer.stop()
            
    def browse_directory(self):
        # self.output_dir = QFileDialog.getExistingDirectory(self, "Select Directory")
        # self.browse_button.setText(self.output_dir)
        # if not self.output_dir:
        #     self.browse_button.setText("Browse")
        # # if self.output_dir:
        # #     print(f"Output directory selected: {self.output_dir}")
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Save CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_name:
            self.csv_file_path = file_name
            self.browse_button.setText(self.csv_file_path)
            print(f"CSV file path: {self.csv_file_path}")
        else:
            print("No CSV file selected.")
            

    def save_data_to_csv(self):
        file_path = self.csv_file_path
        with open(file_path, "w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            header = ["Time"] + [f"Channel_{channel + 1}" for channel in range(self.num_channels)]
            csv_writer.writerow(header)  # Write header
            csv_writer.writerows(self.logdata)

    def start_recording_data(self):
        # timestamp = int(time.perf_counter() * 1000)
        recorded_data = dz
        if timestamp != self.temp_timestamp:
            self.record_data(timestamp,recorded_data)
            self.temp_timestamp = timestamp
        time.sleep(0.001)

    def record_data(self, time, logdata):
        if self.recordStatus:
            self.logdata.append([time]+logdata.tolist())

    def serialplot(self):
        if not self.serialplotStatus:
            self.serialplotStatus = True
            self.serialplot_button.setText("Heatmap")
            self.stacked_widget.setCurrentWidget(self.serial_plot_widget)
            self.start_button.hide()
        else:
            self.serialplotStatus = False
            self.stacked_widget.setCurrentWidget(self.heatmap_widget)
            self.serialplot_button.setText("Serial Plot")
            self.start_button.show()


def calcValues():
    global average, dz
    for taxel in range(0, Taxels):
        # print(dz[[4*taxel,4*taxel+1,4*taxel+2,4*taxel+3]])
        c1_new = dz[4*taxel] + dz[4*taxel+1]
        c3_new = dz[4*taxel+2] + dz[4*taxel+3]
        c1_avg = average[4*taxel] + average[4*taxel+1]
        c3_avg = average[4*taxel+2] + average[4*taxel+3]
        shear_vals_y[taxel] =  (c3_avg*c1_new - c1_avg*c3_new)/(c3_new+c1_new)*-1

        c2_new = dz[4*taxel] + dz[4*taxel+2]
        c4_new = dz[4*taxel+1] + dz[4*taxel+3]
        c2_avg = average[4*taxel] + average[4*taxel+2]
        c4_avg = average[4*taxel+1] + average[4*taxel+3]
        shear_vals_x[taxel] = (c4_avg*c2_new - c2_avg*c4_new)/(c4_new+c2_new)

        pressure_vals[taxel] = (c1_new + c3_new - c1_avg - c3_avg)/4
        # print(pressure_vals)

class SerialPlotWidget(QWidget):
    global dz, timestamp
    def __init__(self):
        super().__init__()

        self.selected_channels = [1,2,3,4]
        self.legend = None

        # Set up the figure and axis for the serial plot
        self.figure, self.ax = plt.subplots()
        self.lines = [self.ax.plot([], [], label=f"Channel {i}")[0] for i in self.selected_channels]
        self.ax.set_xlabel('Time')
        self.ax.set_ylabel('Raw Count')
        self.ax.legend()
        

        # Set up the data and time arrays
        self.data = [[] for _ in range(len(self.selected_channels))]
        self.time = []

        self.channel_checkboxes = [QCheckBox() for i in range(4)]
        for i, checkbox in enumerate(self.channel_checkboxes):
            
            checkbox.setChecked(True)

            # Connect the combobox signal to the update_channel_selection function
            checkbox.stateChanged.connect(self.update_channel_visibility)

        # Create three QComboBoxes for channel selection
        self.channel_comboboxes = [QComboBox() for _ in range(4)]
        for i, combobox in enumerate(self.channel_comboboxes):
            # combobox.addItem(f"Select Channel {i + 1}...")
            for channel in range(Channels-1):
                combobox.addItem(f"Channel {channel + 1}")

            combobox.setCurrentIndex(i)

            # Connect the combobox signal to the update_channel_selection function
            combobox.currentIndexChanged.connect(self.update_channel_selection)

        # Create an QHBoxLayout for the comboboxes
        channel_layout = QHBoxLayout()
        for checkbox, combobox in zip(self.channel_checkboxes, self.channel_comboboxes):
            channel_h_layout = QHBoxLayout()
            channel_h_layout.addWidget(checkbox)
            channel_h_layout.addWidget(combobox)
            channel_layout.addLayout(channel_h_layout)

        # Create a timer to update the plot at regular intervals
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # Update plot every 50 ms
        

        # Add the canvas to the widget
        layout = QVBoxLayout(self)
        layout.addWidget(FigureCanvas(self.figure))
        layout.addLayout(channel_layout)

        self.max_array_size = 1000
        

    def update_plot(self):
        # In this example, we'll use a simple sine wave as an example data source
        time = timestamp * 0.001  # Time in seconds
        dzlist = dz.tolist()
        rawcount = [dzlist[i-1] for i in self.selected_channels]
        # print(self.selected_channels)
        # Append the new data to the arrays
        self.time.append(time)
        for i in range(len(self.lines)):
            self.data[i].append(rawcount[i])

        if len(self.time) > self.max_array_size:
            self.time.pop(0)
            for i in range(len(self.lines)):
                self.data[i].pop(0)

        # Update the plot data for each channel
        for i in range(len(self.lines)):
            self.lines[i].set_data(self.time, self.data[i])
            self.ax.relim()
            self.ax.autoscale_view()
        self.ax.set_xlim(max(0, time - 10), time + 1)
        # Redraw the plot
        self.figure.canvas.draw()

    def update_channel_selection(self):
        self.selected_channels = []
        for combobox in self.channel_comboboxes:
            selected_index = combobox.currentIndex()
            if 0 <= selected_index < Channels:
                self.selected_channels.append(selected_index+1)

        # Check if the total number of selected channels exceeds the maximum limit
        # if len(selected_channels) > self.max_selected_channels:
        #     for combobox in self.channel_comboboxes:
        #         combobox.setEnabled(False)
        #     return

        # Enable all comboboxes if the total selected channels are within the limit
        for combobox in self.channel_comboboxes:
            combobox.setEnabled(True)

        # Hide lines of unselected channels and show lines of selected channels
        # for i, line in enumerate(self.lines):
        #     line.set_visible(i in self.selected_channels)

        self.data = [[] for _ in range(len(self.selected_channels))]
        self.time = []

        visible_lines = [line for line, checkbox in zip(self.lines, self.channel_checkboxes) if checkbox.isChecked()]
        visible_labels = [f"Channel {self.selected_channels[i]}" for i, checkbox in enumerate(self.channel_checkboxes) if checkbox.isChecked()]
        print(self.selected_channels)
        if self.legend is not None:
            self.legend.remove()
        # Redraw the plot
        # print(visible_labels)
        self.ax.legend(visible_lines,visible_labels)
        
        self.figure.canvas.draw()


        # Redraw the plot
        self.figure.canvas.draw()

    def update_channel_visibility(self):
        visible_channels =  [i for i, checkbox in enumerate(self.channel_checkboxes) if checkbox.isChecked()]
        for i in range(len(self.lines)):
            self.lines[i].set_visible(i in visible_channels)
        visible_lines = [line for line, checkbox in zip(self.lines, self.channel_checkboxes) if checkbox.isChecked()]
        visible_labels = [f"Channel {self.selected_channels[i]}" for i, checkbox in enumerate(self.channel_checkboxes) if checkbox.isChecked()]
        if self.legend is not None:
            self.legend.remove()
        # Redraw the plot
        # print(visible_labels)
        self.ax.legend(visible_lines,visible_labels)
        
        self.figure.canvas.draw()


def select_com_port():
        
        
        available_ports = list(serial.tools.list_ports.comports())

        if not available_ports:
            messagebox.showinfo("No COM ports found", "No COM ports found.")
        else:
            root = tk.Tk()
            root.title("Select COM Port")
            
            # Set the window size
            root.geometry("400x300")

            label = tk.Label(root, text="Available COM ports:")
            label.pack()

            listbox = tk.Listbox(root, height=10, width=50)  # Set height and width
            listbox.pack()

            for i, port in enumerate(available_ports, 1):
                listbox.insert(tk.END, f"{i}. {port.device} - {port.description}")

            def on_select():
                global flag_COM,portNum
                selection = listbox.curselection()
                if len(selection) == 1:
                    selected_port = available_ports[selection[0]].device
                    root.destroy()
                    flag_COM = False
                    portNum = str(selected_port)
                    # messagebox.showinfo("COM Port Selected", f"You selected {selected_port}.")
                else:
                    messagebox.showinfo("Invalid Selection", "Please select a COM port.")
                    root.destroy()

                

            button = tk.Button(root, text="Select", command=on_select)
            button.pack()

            root.mainloop()

if __name__ == "__main__":
    import sys

    select_com_port()
    print(portNum)    
    #***********************Code start here**********************************#
    # Initialize serial port
    
    ser = serial_port_init(portNum)
    #Initialize settings for plotting

    # define values for calculating average at the beginning
    index = 0
    i = 0
    count = 0
    input_val = np.zeros((100, Channels))
    average = np.zeros(Channels)

    while index < 100:
        line = ser.readline()
        data = line.decode()
        word = data.split(",")
        len_word = len(word)
        count = count + 1
        if(len_word >= Channels): # check value
            for i in range(Channels):
                input_val[index][i] = float(word[i])
            index = index + 1


    for i in range(Channels):
        total = 0
        for index in range(100):
            total = input_val[index][i] + total
            average_val = total / 100
            average [i] = average_val

    thread = Thread(target = thread1)
    thread.setDaemon(True)
    thread.start()
    time.sleep(0.01)
    # calcValues()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setGeometry(100, 100, 800, 600)
    window.show()
    sys.exit(app.exec_())
