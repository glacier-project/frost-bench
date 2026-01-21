#!/usr/bin/env python3
"""
Compare task durations between two simulation result files.
"""
import argparse
import json
from collections import defaultdict
import matplotlib.pyplot as plt


def load_task_durations(filepath: str) -> dict[str, list[int]]:
    """Load task durations from a result file.
    
    Returns a dict mapping task name to list of durations (end_time - start_time).
    """
    with open(filepath) as f:
        data = json.load(f)
    
    task_durations = defaultdict(list)
    
    for machine_name, tasks in data.get("mapping", {}).items():
        for entry in tasks:
            task_name = entry["task"]["name"]
            if task_name == "WaitPalletAtSegment":
                continue
            duration = entry["end_time"] - entry["start_time"]
            task_durations[task_name].append(duration)
    
    return task_durations


def plot_distributions(file1: str, file2: str) -> None:
    """Plot duration distributions for each task comparing two files."""
    durations1 = load_task_durations(file1)
    durations2 = load_task_durations(file2)
    
    # Extract metric names from filenames
    def extract_metric(filepath: str) -> str:
        import re
        match = re.search(r'_(None|DistanceMetric)_', filepath)
        return match.group(1) if match else filepath
    
    label1 = extract_metric(file1)
    label2 = extract_metric(file2)
    
    # Get all unique task names
    all_tasks = sorted(set(durations1.keys()) | set(durations2.keys()))
    
    n_tasks = len(all_tasks)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()
    
    for idx, task in enumerate(all_tasks[:4]):  # Max 4 tasks for 2x2 grid
        ax = axes[idx]
        
        data1 = durations1.get(task, [])
        data2 = durations2.get(task, [])
        
        # Create violin plots
        if data1 and data2:
            parts = ax.violinplot([data1, data2], positions=[1, 2], showmeans=True, showmedians=True)
            
            # Color the violins
            colors = ['steelblue', 'coral']
            for i, pc in enumerate(parts['bodies']):
                pc.set_facecolor(colors[i])
                pc.set_edgecolor('black')
                pc.set_alpha(0.7)
            
            # Style the lines
            for partname in ['cmeans', 'cmedians', 'cbars', 'cmins', 'cmaxes']:
                if partname in parts:
                    parts[partname].set_edgecolor('black')
            
            ax.set_xticks([1, 2])
            ax.set_xticklabels([
                f'{label1}\n(n={len(data1)}, μ={sum(data1)/len(data1):.1f})',
                f'{label2}\n(n={len(data2)}, μ={sum(data2)/len(data2):.1f})'
            ])
        elif data1:
            parts = ax.violinplot([data1], positions=[1], showmeans=True, showmedians=True)
            parts['bodies'][0].set_facecolor('steelblue')
            parts['bodies'][0].set_alpha(0.7)
            ax.set_xticks([1])
            ax.set_xticklabels([f'{label1}\n(n={len(data1)})'])
        elif data2:
            parts = ax.violinplot([data2], positions=[1], showmeans=True, showmedians=True)
            parts['bodies'][0].set_facecolor('coral')
            parts['bodies'][0].set_alpha(0.7)
            ax.set_xticks([1])
            ax.set_xticklabels([f'{label2}\n(n={len(data2)})'])
        
        ax.set_title(f'{task}')
        ax.set_ylabel('Duration')
        ax.grid(True, alpha=0.3, axis='y')
    
    # Hide unused subplots
    for idx in range(len(all_tasks), 4):
        axes[idx].set_visible(False)
    
    fig.suptitle(f'Task Duration Distributions\n{label1} vs {label2}', fontsize=10)
    plt.tight_layout()
    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Compare task durations between two simulation result files.')
    parser.add_argument('file1', type=str, help='First JSON result file')
    parser.add_argument('file2', type=str, help='Second JSON result file')
    args = parser.parse_args()
    
    plot_distributions(args.file1, args.file2)


if __name__ == "__main__":
    main()
