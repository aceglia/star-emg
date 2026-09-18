import os
import subprocess
import serial.tools.list_ports
import re

def get_existing_ports(setupc_path):
    # get actual ports
    ports = serial.tools.list_ports.comports()
    existing_real = {port.device for port in ports}

    # get com0com ports
    list_port_cmd = [setupc_path, "list"]
    result = subprocess.run(
        list_port_cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    # find in txt all instance of COM***
    existing_com0com = set(re.findall(r"COM\d+", result.stdout))
    return existing_real.union(existing_com0com)

def create_com0com_pairs(
    n_pairs: int = 10,
    signal_start: int = 10,
    talker_start: int = 110,
):
    setupc = os.path.join("C:\\", "Program Files (x86)", "com0com", "setupc.exe")

    if not os.path.exists(setupc):
        raise FileNotFoundError(setupc)
    existing = get_existing_ports(setupc)

    for i in range(n_pairs):
        signal_port = f"COM{signal_start + i}"
        talker_port = f"COM{talker_start + i}"
        if signal_port in existing or talker_port in existing:
            continue
        cmd = [
            str(setupc),
            "install "
            f"PortName={signal_port} "
            f"PortName={talker_port}",
        ]

        print(" ".join(cmd))

        subprocess.run(
            cmd,
            cwd=r"C:\Program Files (x86)\com0com",
            check=True,
            capture_output=False,
            text=False,
        )

if __name__ == "__main__":
    create_com0com_pairs()