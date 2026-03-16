# USB Power Pin Warning

## The Problem

When you connect a USB cable between a Raspberry Pi and an Ender 3 S1 Pro, the USB cable carries 5V power through pin 1 of the USB-A connector. This causes several problems:

1. **The printer's control board stays powered** even when the printer is "off" (you'll see the screen light up)
2. **Electrical interference** can cause serial communication errors during printing
3. **Potential damage** to either the Pi or printer's control board from back-feeding power

## The Solution

You MUST block the 5V power pin before connecting the USB cable.

### Method 1: Electrical Tape (Easiest)

1. Look at the USB-A connector (the flat rectangular end)
2. With the connector facing you and contacts visible, the 5V pin is the **rightmost** pin
3. Place a small piece of **electrical tape** over just that pin
4. The tape should cover ONLY the rightmost pin, not the other 3 pins
5. Plug in the cable

### Method 2: USB Power Blocker Dongle

Buy a "USB power blocker" or "USB data-only adapter" - these are small dongles that physically disconnect the 5V line. Available for a few dollars on Amazon.

### Method 3: Cut the Wire (Permanent)

If you have a spare USB cable dedicated to the printer:
1. Carefully cut open the cable sheath
2. Cut the **red wire** (this is the 5V power line)
3. Leave the black (ground), white (D-), and green (D+) wires intact
4. Tape up the cable

## How to Verify

After applying the fix:
1. Turn off the printer (power switch off)
2. Connect the USB cable to the Pi
3. The printer screen should stay OFF
4. If the screen lights up, the 5V is still getting through - check your tape/blocker
