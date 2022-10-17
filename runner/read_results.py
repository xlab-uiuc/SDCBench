import argparse

parser = argparse.ArgumentParser(description='Run SDC tools')
parser.add_argument('--file', type=str, required=True, default='results.txt', help='File to read')
args = parser.parse_args()

try:
    total_execution_time = 0
    with open(args.file, 'r') as f:
        for l in f.readlines():
            l = l.strip()
            if 'execution_time' in l:
                s = l.split(' ')[1]
                s = s[:-1]
                execution_time = float(s)
                total_execution_time += execution_time
    print(f'Total execution time in seconds: {total_execution_time}')
    print(f'Total execution time in hours: {total_execution_time / 3600}')

except Exception as e:
    print(f'{e}')