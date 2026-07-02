# Telemetry Collector and Filtering Analyser

The purpose of this project is to interface with an ESP32 micro-controller to acquire, calibrate, and filter ultrasonic sensor distance measurements. It consists of two components: a serial collector that interfaces with the hardware node to record raw duration and distance telemetry, and a post-processing data analyser that applies a series of digital signal processing filters (including moving average, median filters, exponential moving averages, a hybrid median-EMA filter, a Kalman filter, and Median Absolute Deviation outlier detection) to the telemetry datasets. The analyser calibrates the raw measurements using linear regression based on standard speed of sound propagation (340 m/s) and outputs statistical CSV datasets and comparative performance plots for filter benchmarking.

## Prerequisites

Before running the scripts, ensure you have Python 3 installed along with the required dependencies. You can install the dependencies via pip:

```bash
pip install -r requirements.txt
```

## Tools and Usage

### 1. Serial Telemetry Collector (`serial_collector.py`)

This script establishes a serial connection with the ESP32 micro-controller to record duration and distance data. The collected telemetry is buffered in memory and saved to disk.

#### How to Run
```bash
python serial_collector.py
```

#### Steps for Operation
1. **Connect to Port:** Upon execution, the script prompts for the serial port (e.g., `COM3` on Windows or `/dev/ttyUSB0` on Linux/macOS). Press enter to select the default (`COM3`).
2. **Interactive Command Console:** Once connected, the console enters an interactive loop expecting one of the following commands:
   - `start <height_cm>`: Initiates data collection at the specified true/target distance (e.g., `start 10.0`). The system collects a batch of 50 samples at this position.
   - `stop`: Halts recording, saves the buffered data to `data/raw_data.csv`, and clears the local telemetry buffer.
   - `reset`: Resets the telemetry buffer in memory.
   - `exit`: Disconnects from the serial port and exits the program.
   - *Other Inputs:* Any other input string will be forwarded as a command directly to the ESP32 micro-controller.
3. **Data Collection Workflow:**
   - Execute `start <height_cm>` for the first calibration point.
   - Wait for the batch of 50 samples to complete.
   - Adjust the hardware/target height.
   - Execute `start <next_height_cm>` for the next height.
   - When all points have been measured, type `stop` to save the dataset.

---

### 2. Data Analyser (`data_analyser.py`)

This post-processing script loads the raw telemetry collected by `serial_collector.py`, performs calibration regression, applies multiple digital filters, and generates performance visualizations.

#### How to Run
```bash
python data_analyser.py
```

#### Analysis Steps & Outputs
1. **Calibration:** The script fits a linear regression equation (`True_Distance = slope * Raw_Sensor + intercept`) using a standard speed of sound (340 m/s) and outputs the calibration equation parameters to the console.
2. **Filtering:** Applies the following filtering algorithms to the raw distance data:
   - **Moving Average:** Window size of 5.
   - **Median Filter:** Window sizes of 5 and 7.
   - **Exponential Moving Average (EMA):** Alpha values of 0.2 and 0.5.
   - **Hybrid Filter:** An EMA filter (alpha = 0.2) applied on the output of a Median filter (window size 5).
   - **Kalman Filter:** Process noise covariance Q = 1e-4, measurement noise covariance R = 0.1.
   - **Median Absolute Deviation (MAD):** Outlier detection window size of 5 with threshold 2.5, replacing outliers with window mean.
3. **Output Files:**
   - **`data/processed_standard.csv`:** Contains the original timestamps, actual distances, raw sensor measurements, calibrated regression values, and filtered outputs for all algorithms.
   - **`data/benchmark_standard_samples.png`:** A single plot showing the true target distance compared against raw, calibrated, and all filtered data across all sample points.
   - **`data/benchmark_standard.png`:** A 2x2 grid subplot displaying:
     - Raw sensor data vs. true distance.
     - Median filter comparisons (window sizes 5 vs. 7).
     - Continuous smoothing filters (EMA, Hybrid, Kalman).
     - Zoomed error comparison relative to the true distance.

