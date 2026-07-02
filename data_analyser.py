import os
import sys
import csv
import numpy as np
import matplotlib.pyplot as plt

class DataAnalyser:
    def __init__(self, raw_csv_path='data/raw_data.csv'):
        self.raw_csv_path = raw_csv_path
        self.raw_data = []

    def load_data(self):
        if not os.path.exists(self.raw_csv_path):
            print(f"Error: {self.raw_csv_path} not found. Please run the collector first.")
            return False
        
        with open(self.raw_csv_path, 'r') as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            for row in reader:
                if not row or len(row) < 3:
                    continue
                try:
                    ts = int(row[0])
                    dur = int(row[1])
                    act = float(row[2])
                    self.raw_data.append((ts, dur, act))
                except ValueError:
                    continue
        print(f"Loaded {len(self.raw_data)} data points from {self.raw_csv_path}")
        return len(self.raw_data) > 0

    def process_and_plot(self):
        # Extract columns
        timestamps = [r[0] for r in self.raw_data]
        durations = [r[1] for r in self.raw_data]
        actuals = [r[2] for r in self.raw_data]

        # Convert raw durations to distance using standard speed of sound (340 m/s)
        raw_dist = [dur * 0.034 / 2.0 for dur in durations]

        # Fits: True_Distance = slope * Raw_Sensor + intercept
        slope, intercept = np.polyfit(raw_dist, actuals, 1)
        reg_dist = [slope * r + intercept for r in raw_dist]

        print("\n--- Calibration Regression Equations ---")
        print(f"Standard (340 m/s): Calibrated_Dist = {slope:.5f} * Raw_340 + ({intercept:.4f})")
        print("----------------------------------------\n")

        # Apply filtering models
        avg_5 = self.moving_average(raw_dist, 5)
        med_5 = self.median_filter(raw_dist, 5)
        med_7 = self.median_filter(raw_dist, 7)
        ema_2 = self.ema_filter(raw_dist, 0.2)
        ema_5 = self.ema_filter(raw_dist, 0.5)
        hybrid = self.ema_filter(med_5, 0.2)
        kalman = self.kalman_filter(raw_dist, Q=1e-4, R=0.1)
        mad = self.mad_outlier_mean(raw_dist, window_size=5, threshold=2.5)

        # Save processed data
        os.makedirs('data', exist_ok=True)
        processed_csv_path = 'data/processed_standard.csv'
        with open(processed_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'actual', 'raw_340',
                'average_5', 'median_5', 'median_7', 'ema_0.2', 
                'ema_0.5', 'hybrid_med_ema', 'kalman', 'mad_filter', 'regression_calibrated'
            ])
            for i in range(len(timestamps)):
                writer.writerow([
                    timestamps[i], actuals[i], raw_dist[i],
                    avg_5[i], med_5[i], med_7[i], ema_2[i],
                    ema_5[i], hybrid[i], kalman[i], mad[i], reg_dist[i]
                ])
        print(f"Processed calibration and filtering data saved to {processed_csv_path}")

        # Render benchmark plots (both samples mode and time mode)
        samples_plot_path = 'data/benchmark_standard_samples.png'
        self.plot_comparison(
            timestamps, actuals, raw_dist, avg_5, med_5, med_7, 
            ema_2, hybrid, kalman, mad, reg_dist, 
            "Standard 340 m/s - Samples", samples_plot_path, x_axis_mode='samples'
        )

        time_plot_path = 'data/benchmark_standard.png'
        self.plot_comparison(
            timestamps, actuals, raw_dist, avg_5, med_5, med_7, 
            ema_2, hybrid, kalman, mad, reg_dist, 
            "Standard 340 m/s - Time", time_plot_path, x_axis_mode='time'
        )

    @staticmethod
    def moving_average(data, window_size):
        filtered = []
        for i in range(len(data)):
            window = data[max(0, i - window_size + 1): i + 1]
            filtered.append(sum(window) / len(window))
        return filtered

    @staticmethod
    def median_filter(data, window_size):
        filtered = []
        for i in range(len(data)):
            window = data[max(0, i - window_size + 1): i + 1]
            filtered.append(sorted(window)[len(window)//2])
        return filtered

    @staticmethod
    def ema_filter(data, alpha):
        filtered = []
        if not data:
            return filtered
        current = data[0]
        for val in data:
            current = alpha * val + (1.0 - alpha) * current
            filtered.append(current)
        return filtered

    @staticmethod
    def kalman_filter(data, Q=1e-4, R=0.1):
        filtered = []
        if not data:
            return filtered
        x_hat = data[0]
        P = 1.0
        for val in data:
            x_hat_minus = x_hat
            P_minus = P + Q
            K = P_minus / (P_minus + R)
            x_hat = x_hat_minus + K * (val - x_hat_minus)
            P = (1 - K) * P_minus
            filtered.append(x_hat)
        return filtered

    @staticmethod
    def mad_outlier_mean(data, window_size=5, threshold=2.5):
        filtered = []
        for i in range(len(data)):
            window = data[max(0, i - window_size + 1): i + 1]
            if len(window) < 3:
                filtered.append(sum(window) / len(window))
                continue
            
            med = sorted(window)[len(window)//2]
            deviations = [abs(x - med) for x in window]
            mad = sorted(deviations)[len(deviations)//2]
            if mad == 0:
                mad = 1e-5
            
            clean_window = []
            for x in window:
                z_score = abs(x - med) / mad
                if z_score <= threshold:
                    clean_window.append(x)
            
            if not clean_window:
                clean_window = [med]
            filtered.append(sum(clean_window) / len(clean_window))
        return filtered

    def plot_comparison(self, ts, actuals, raw_dist, avg_5, med_5, med_7, ema_2, hybrid, kalman, mad, reg, title_suffix, filename, x_axis_mode='samples'):
        N = len(ts)
        if x_axis_mode == 'time':
            x_values = [(t - ts[0]) / 1000.0 for t in ts]
            x_label = 'Time (seconds)'
        else:
            x_values = list(range(1, N + 1))
            x_label = 'Sample Number'

        plt.figure(figsize=(12, 7))
        plt.plot(x_values, actuals, color='#2d6a4f', label='True Distance (Target)', linewidth=3, linestyle='--')
        plt.scatter(x_values, raw_dist, color='#f28482', label='Raw Sensor', alpha=0.5, s=15, edgecolors='none')
        
        plt.plot(x_values, avg_5, color='#60a5fa', label='Mean (5)', linewidth=1.5)
        plt.plot(x_values, med_5, color='#1d3557', label='Median (5)', linewidth=1.5)
        plt.plot(x_values, med_7, color='#457b9d', label='Median (7)', linewidth=1.5, linestyle=':')
        plt.plot(x_values, ema_2, color='#f4a261', label='EMA (α=0.2)', linewidth=1.5)
        plt.plot(x_values, hybrid, color='#7209b7', label='Hybrid Median→EMA', linewidth=2)
        plt.plot(x_values, kalman, color='#00b4d8', label='Kalman Filter', linewidth=2, linestyle='-.')
        plt.plot(x_values, mad, color='#a3e635', label='MAD Outlier + Average', linewidth=1.5)
        plt.plot(x_values, reg, color='#e63946', label='Linear Regression Calibrated', linewidth=2.5)

        plt.title(f'Ultrasonic Sensor Calibration & Filtering Benchmark\n({title_suffix})', fontsize=14, fontweight='bold')
        plt.ylabel('Distance (cm)', fontsize=11)
        plt.xlabel(x_label, fontsize=11)
        plt.grid(True, linestyle=':', alpha=0.5)
        plt.legend(loc='upper right', framealpha=0.9, facecolor='#ffffff')
        
        ax = plt.gca()
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        print(f"Benchmark plot saved to {filename}")
        plt.show()

def main():
    analyser = DataAnalyser()
    if analyser.load_data():
        analyser.process_and_plot()

if __name__ == "__main__":
    main()
