from django.core.management.base import BaseCommand
from campus.security_service import run_scan

class Command(BaseCommand):
    help='Collect bounded local security evidence; --daily reuses today’s snapshot.'
    def add_arguments(self,parser):parser.add_argument('--daily',action='store_true')
    def handle(self,*args,**options):
        scan=run_scan(daily=options['daily'])
        self.stdout.write(f'Date {scan.day}; score {scan.score}/100; check coverage {scan.coverage}%')
