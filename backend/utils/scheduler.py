
# TODO: Implement scheduling utilities. [Milestone: Scheduling]

from apscheduler.schedulers.background import BackgroundScheduler

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Add jobs here
    scheduler.start()