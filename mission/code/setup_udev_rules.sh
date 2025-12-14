#!/bin/bash

# Script to set up udev rules for USB devices (ttyACM)
# This allows access to /dev/ttyACM devices without sudo

echo "Setting up udev rules for USB devices..."

# Create udev rule file
sudo tee /etc/udev/rules.d/99-ttyacm-permissions.rules > /dev/null << 'EOF'
# Allow access to ttyACM devices for dialout group
KERNEL=="ttyACM[0-9]*", MODE="0666", GROUP="dialout"
EOF

# Add user to dialout group if not already added
if ! groups | grep -q dialout; then
    echo "Adding user to dialout group..."
    sudo usermod -aG dialout $USER
    echo "✓ Added $USER to dialout group"
    echo ""
    echo "IMPORTANT: You need to log out and log back in for group changes to take effect."
    echo "Or run: newgrp dialout"
else
    echo "✓ User already in dialout group"
fi

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

echo ""
echo "✓ Udev rules installed successfully"
echo ""
echo "After logging out/in (or running 'newgrp dialout'), you won't need sudo for /dev/ttyACM devices"

