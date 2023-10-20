import subprocess
import requests
import time
import os

ReportHourlyTimer = time.time() + 3600

def sendReport(name):
    t = open("/proc/cpuinfo", "r").read()
    SN="Unknown"
    for l in t.split("\n"):
        if 'Serial' in l:
            SN = l[-8:]
    print("Serial: {}".format(SN))
    res = subprocess.run(['journalctl', '-u', name, '-n', '100'], stdout=subprocess.PIPE).stdout.decode('utf-8')
    if "Traceback" not in res:
        print("Skip sending report")
        return
    print("Sending report")
    content = "Serial: {}\n".format(SN)+res
    r = requests.post('https://repo.larnitech.com/serversLogs/crash.php?name='+name, data=content.encode('utf-8'), headers={'Content-Type': 'text/html', 'Accept-Charset': 'UTF-8'})
    if r.status_code == requests.codes.ok:
        print("Report successfuly sent")
    else:
        print("Error sending report. Code: {}".format(r.status_code))
    return

def hourlyReport(fname):
    global ReportHourlyTimer

    if ReportHourlyTimer<time.time():
        ReportHourlyTimer = time.time() + 3600
        if os.path.exists(fname):
            t = open("/proc/cpuinfo", "r").read()
            SN="Unknown"
            for l in t.split("\n"):
                if 'Serial' in l:
                    SN = l[-8:]
            print("Serial: {}".format(SN))
            content = "Serial: {}\n".format(SN)+open(fname, "r").read(65536)
            r = requests.post('https://repo.larnitech.com/serversLogs/crash.php?name=crashes', data=content.encode('utf-8'), headers={'Content-Type': 'text/html', 'Accept-Charset': 'UTF-8'})
            os.remove(fname)
