import serial.tools.list_ports
import time
import random
import sys
import re
import json
from Adafruit_IO import MQTTClient

# Điền Username và Key của bạn vào đây
AIO_USERNAME = ""
AIO_KEY = ""

# Feed bbc-sensor dùng để nhận chuỗi JSON tổng hợp
AIO_FEED_ID = ["bbc-fan", "bbc-pump", "bbc-mode"] 

# Biến toàn cục lưu trữ trạng thái hệ thống
device_data = {
    "temperature": 0.0,
    "air_humidity": 0.0,
    "soil_moisture": 0.0,
    "light_intensity": 0.0,
    "pump": False,
    "fan": False,
    "mode": "manual"
}

# ----------------- HÀM GỬI JSON TỔNG HỢP -----------------
def publish_json_payload():
    payload = {
        "device_source": "YOLOFARM_001",
        "sensor": {
            "temperature":    { "value": device_data["temperature"], "unit": "°C", "MAX": 32,  "MIN": 18 },
            "air_humidity":   { "value": device_data["air_humidity"], "unit": "%",  "MAX": 85,  "MIN": 50 },
            "soil_moisture":  { "value": device_data["soil_moisture"], "unit": "%",  "MAX": 80,  "MIN": 30 },
            "light_intensity":{ "value": device_data["light_intensity"], "unit": "%",  "MAX": 85,  "MIN": 75 }
        },
        "status": {
            "fan":  device_data["fan"],
            "pump": device_data["pump"],
            "mode": device_data["mode"]
        }
    }
    json_payload = json.dumps(payload)
    print("Dữ liệu JSON đồng bộ: ", json_payload)
    client.publish("bbc-sensor", json_payload) # Gửi lên bbc-sensor theo yêu cầu

# ----------------- XỬ LÝ DỮ LIỆU TỪ SERIAL (CẢM BIẾN) -----------------
def handle_serial_data(data):
    global device_data
    update_sensor = False
    update_status = False # Cờ báo hiệu có thay đổi trạng thái bơm/quạt từ mạch
    
    for key, value in data:
        try:
            k = key.strip()
            v = float(value.strip())
            
            # Xử lý cảm biến
            if k == "TEMP":
                device_data["temperature"] = v
                update_sensor = True
            elif k == "HUMID":
                device_data["air_humidity"] = v
                update_sensor = True
            elif k == "MOISTURE":
                device_data["soil_moisture"] = v
                update_sensor = True
            elif k == "LIGHT":
                device_data["light_intensity"] = v
                update_sensor = True
                
            # Xử lý cập nhật trạng thái thiết bị gửi từ Yolo:Bit (đặc biệt khi ở chế độ Auto)
            elif k == "FAN":
                new_fan_state = True if v == 1 else False
                if device_data["fan"] != new_fan_state:
                    device_data["fan"] = new_fan_state
                    update_status = True
                    
            elif k == "PUMP":
                new_pump_state = True if v == 1 else False
                if device_data["pump"] != new_pump_state:
                    device_data["pump"] = new_pump_state
                    update_status = True
                    
            elif k == "MODE":
                new_mode = "manual" if v == 1 else "auto"
                if device_data["mode"] != new_mode:
                    device_data["mode"] = new_mode
                    update_status = True

        except ValueError:
            print("Dữ liệu không hợp lệ: ", key, "= ", value)
            
    # Nếu có cảm biến hoặc trạng thái thiết bị thay đổi thì cập nhật gói JSON
    if update_sensor or update_status:
        publish_json_payload()

# ----------------- XỬ LÝ DỮ LIỆU TỪ MQTT (ĐIỀU KHIỂN) -----------------
def message(client, feed_id, payload):
    global device_data
    print(f"Nhận lệnh từ {feed_id}: {payload}")
    update_device = False

    if feed_id == "bbc-fan":
        if payload == "True" or payload == "1":
            print("BẬT QUẠT")
            device_data["fan"] = True
            if isMicrobitConnected: ser.write("A".encode())
            update_device = True
        elif payload == "False" or payload == "0":
            print("TẮT QUẠT")
            device_data["fan"] = False
            if isMicrobitConnected: ser.write("a".encode())
            update_device = True

    elif feed_id == "bbc-pump":
        if payload == "True" or payload == "1":
            print("BẬT BƠM")
            device_data["pump"] = True
            if isMicrobitConnected: ser.write("B".encode())
            update_device = True
        elif payload == "False" or payload == "0":
            print("TẮT BƠM")
            device_data["pump"] = False
            if isMicrobitConnected: ser.write("b".encode())
            update_device = True

    elif feed_id == "bbc-mode":
        if payload == "auto":
            print("CHẾ ĐỘ AUTO")
            device_data["mode"] = "auto"
            if isMicrobitConnected: ser.write("C".encode()) # C: Auto
            update_device = True
        elif payload == "manual":
            print("CHẾ ĐỘ MANUAL")
            device_data["mode"] = "manual"
            if isMicrobitConnected: ser.write("c".encode()) # c: Manual
            update_device = True

    # Đồng bộ lại JSON nếu có sự thay đổi trạng thái thiết bị
    if update_device:
        publish_json_payload()

# ----------------- CÁC HÀM MQTT CƠ BẢN -----------------
def connected(client):
    print("Kết nối thành công tới Adafruit IO ...")
    for feed_id in AIO_FEED_ID:
        client.subscribe(feed_id)

def subscribe(client, userdata, mid, granted_qos):
    print("Subscribe thành công ...")

def disconnected(client):
    print("Ngắt kết nối ...")
    sys.exit(1)

# Khởi tạo MQTT
client = MQTTClient(AIO_USERNAME, AIO_KEY)
client.on_connect = connected
client.on_disconnect = disconnected
client.on_message = message
client.on_subscribe = subscribe
client.connect()
client.loop_background()

# ----------------- KẾT NỐI SERIAL & ĐỌC DỮ LIỆU -----------------
def getPort():
     ports = serial.tools.list_ports.comports()
     N = len(ports)
     commPort = "None"
     for i in range (0, N):
         port = ports[i]
         strPort = str(port)
         if "USB-Serial" in strPort:
             splitPort = strPort.split(" ")
             commPort = (splitPort[0])
    return commPort

isMicrobitConnected = False
if getPort() != "None":
    try:
        ser = serial.Serial(port=getPort(), baudrate=115200)
        isMicrobitConnected = True
        print(f"Đã kết nối với Yolo:bit tại cổng {getPort()}")
    except Exception as e:
        print("Không thể mở cổng Serial:", e)

mess = ""
def readSerial():
    global mess
    try:
        bytesToRead = ser.inWaiting()
        if (bytesToRead > 0):
            mess = mess + ser.read(bytesToRead).decode("UTF-8")
            
            # Dùng regex để lọc lấy dữ liệu theo format !KEY:VALUE#
            pattern = r"!([^:]+):([^#]+)#"
            data = re.findall(pattern, mess)
            
            if data:
                print("Dữ liệu nhận từ Serial:", data)
                handle_serial_data(data)
                # Xóa dữ liệu mess đã xử lý
                lastIdx = mess.rfind("#")
                if lastIdx != -1:
                    mess = mess[lastIdx+1:]
    except Exception as e:
        print("Lỗi nhận dữ liệu Serial:", e)

# ----------------- VÒNG LẶP CHÍNH -----------------
while True:
    if isMicrobitConnected:
        readSerial()
        time.sleep(1)
    else:
        # Giả lập dữ liệu nếu không có kết nối phần cứng
        print("Không phát hiện kết nối nào")
        time.sleep(1) 
