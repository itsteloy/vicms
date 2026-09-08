"""Import Ageing of Accounts from an Excel workbook."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from vicdashboard.ageing_accounts_xlsx import parse_ageing_accounts_xlsx
from vicdashboard.models import AgeingOfAccountsLine, AgeingOfAccountsReport


class Command(BaseCommand):
    help = 'Import Ageing of Accounts rows from an Excel workbook into the database.'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', type=str, help='Path to the .xlsx file')
        parser.add_argument(
            '--as-of',
            dest='as_of',
            default='',
            help='Report as-of date (YYYY-MM-DD). Defaults to today.',
        )
        parser.add_argument('--note', default='', help='Optional note for the report header')
        parser.add_argument(
            '--replace-latest',
            action='store_true',
            help='Replace the most recent report instead of creating a new snapshot',
        )

    def handle(self, *args, **options):
        path = Path(options['xlsx_path'])
        if not path.exists():
            raise CommandError(f'File not found: {path}')
        if path.suffix.lower() != '.xlsx':
            raise CommandError('File must be an .xlsx workbook.')

        as_of_raw = (options.get('as_of') or '').strip()
        if as_of_raw:
            try:
                as_of_date = date.fromisoformat(as_of_raw)
            except ValueError as exc:
                raise CommandError('--as-of must be YYYY-MM-DD') from exc
        else:
            as_of_date = date.today()

        parsed = parse_ageing_accounts_xlsx(path)
        if not parsed['lines']:
            raise CommandError('No ageing account rows found in the workbook.')

        with transaction.atomic():
            if options.get('replace_latest'):
                report = AgeingOfAccountsReport.objects.order_by('-imported_at').first()
                if report:
                    report.lines.all().delete()
                    report.as_of_date = as_of_date
                    report.note = options.get('note') or ''
                    report.source_filename = parsed['source_filename']
                    report.total_amount = parsed['total_amount']
                    report.total_amount_paid = parsed['total_amount_paid']
                    report.save()
                else:
                    report = AgeingOfAccountsReport.objects.create(
                        as_of_date=as_of_date,
                        note=options.get('note') or '',
                        source_filename=parsed['source_filename'],
                        total_amount=parsed['total_amount'],
                        total_amount_paid=parsed['total_amount_paid'],
                    )
            else:
                report = AgeingOfAccountsReport.objects.create(
                    as_of_date=as_of_date,
                    note=options.get('note') or '',
                    source_filename=parsed['source_filename'],
                    total_amount=parsed['total_amount'],
                    total_amount_paid=parsed['total_amount_paid'],
                )

            AgeingOfAccountsLine.objects.bulk_create([
                AgeingOfAccountsLine(report=report, **line)
                for line in parsed['lines']
            ])

        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(parsed["lines"])} lines into report #{report.id} '
            f'(as of {report.as_of_date}). '
            f'Totals: {report.total_amount} / {report.total_amount_paid}.'
        ))
