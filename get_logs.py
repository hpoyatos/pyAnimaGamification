import subprocess
with open('w_logs.txt', 'w', encoding='utf-8') as f:
    f.write(subprocess.getoutput('docker logs pyanimagamification-selenium_worker-1'))
