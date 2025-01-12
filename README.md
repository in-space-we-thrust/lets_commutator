python pyboard.py --device /dev/ttyUSB0 -c 'raise KeyboardInterrupt'
python pyboard.py --device /dev/ttyUSB0 -f cp firmware/main.py :main.py
python pyboard.py --device /dev/ttyUSB0 -c 'import machine;machine.reset()'

find firmware/ -name "*.py" -type f -exec python pyboard.py --device /dev/ttyUSB0 -f cp {} : \;
find firmware/ -name "sensors.py" -type f -exec python pyboard.py --device /dev/ttyUSB0 -f cp {} : \;