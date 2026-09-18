import numpy as np
import struct
import asyncio
import serial_asyncio as saio
from biosiglive.streaming.utils import CircularBuffer
HEADER_FORMAT = "<BBBBHHI"
start_bytes = b"\xAA\x55"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
INT_scale = 1e8


class BatchLogger:
    def __init__(self, n_channels, n_samples):
        self.t0 = None
        self.full = False
        self.data = np.empty((n_channels, n_samples), dtype=np.float64)
        self.batch_number = 0
        self.channel_counter = 0
    
    def log_batch(self, t0, channel, data):
        if t0 == self.t0:
            self.data[channel, :] = data
            self.channel_counter += 1
        else:
            self.data = np.empty_like(self.data)
            self.t0 = t0
            self.data[channel, :] = data
            self.channel_counter = 1
        return self.channel_counter == self.data.shape[0]  # return True if all channels have been logged


class PacketReader:
    def __init__(self, port, n_channels=None, n_samples=None, dt=0.0005, buff_size = 2000):
        self.int_type = None
        self.channel = None
        self.port = port
        self.frame = None
        self.packet_size = None
        self.n_channels = n_channels
        self.n_samples = n_samples
        self.dt = dt
        self.t0 = None
        self.buffer_size = buff_size
        self.buffer = None if n_channels is None else CircularBuffer(n_channels, self.buffer_size, dtype=np.float64, time_dtype=np.float64, dt=dt)
        self.batch_logger = None if n_samples is None else BatchLogger(n_channels, n_samples)
        self.empty_t = None if n_samples is None else np.linspace(0, n_samples * self.dt, n_samples)
        self.data = None
        self.task = None

    def from_bytes(self, packet):
        if packet == b'':
            return b''
        while True:
            # find the start bytes in the packet
            if len(packet) == 0:
                return b''
            start_index = packet.find(start_bytes)
            if start_index == -1:
                return packet
            # check if there are enough bytes for the header
            if len(packet) < start_index + HEADER_SIZE:
                return packet
            # unpack the header
            packet_header = packet[start_index:start_index + HEADER_SIZE]
            sync_0, sync_1, self.int_type, self.n_channels, frame, self.packet_size, t0_raw = struct.unpack(HEADER_FORMAT, packet_header)
            self.t0 = (frame * 4) + t0_raw / INT_scale
            data = packet[start_index + HEADER_SIZE:start_index + HEADER_SIZE + self.packet_size]
            if len(data) < self.packet_size:
                return packet
            self.data = np.frombuffer(data, dtype=self._get_int_type(self.int_type)).reshape(self.n_channels, -1) / INT_scale
            self.n_samples = self.data.shape[1]
            self._add_to_buffer(self.t0, self.data)
            packet = packet[start_index + HEADER_SIZE + self.packet_size:]
            self.task(self.data, self.empty_t + self.t0) if self.task else None

    async def receiver(self):
        while True:
            try:
                reader, writer = await saio.open_serial_connection(
                    url=self.port,
                    baudrate=921600,
                    timeout=0.5,
                )
                print(f"Connected to {self.port}")
                break
            except Exception as e:
                print(f"Error reading serial: {e}")
                await asyncio.sleep(1)  # wait before retrying
        packet = b''
        while True:
            data = await reader.read(4096)
            packet = self.from_bytes(packet + data)

    def _add_to_buffer(self, t0, data):
        if self.buffer is None: 
            self.buffer = CircularBuffer(self.n_channels, self.buffer_size, dtype=np.float64, time_dtype=np.float64, dt=self.dt)
        if self.empty_t is None:
            self.empty_t = np.arange(0, 20) * self.dt
        self.buffer.append(data, self.empty_t + t0)
    
    def _get_int_type(self, int_type):
        if int_type == 16: 
            return np.int16
        elif int_type == 32:
            return np.int32
        elif int_type == 64:
            return np.int64
        else:
            raise ValueError("Invalid integer type")
    
    def start(self, task: callable = None):
        self.task = task
        asyncio.run(self.receiver())


if __name__ == "__main__":
    # from scipy import signal
    reader = PacketReader('COM110')
    def task(d, t):
        print(t[0])
    reader.start()