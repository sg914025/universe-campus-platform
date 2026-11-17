from django.core.management.base import BaseCommand
from django.db import close_old_connections,OperationalError
from campus.booking_notices import process_attendance
import time
class Command(BaseCommand):
    help='Release overdue unclaimed study seats. Author: UniVerse Team'
    def add_arguments(self,parser):parser.add_argument('--watch',action='store_true')
    def handle(self,*args,**options):
        while True:
            close_old_connections()
            try:
                n=process_attendance()
                if n:self.stdout.write(f'Released {n} overdue bookings')
            except OperationalError as error:self.stderr.write(str(error))
            if not options['watch']:break
            time.sleep(30)
