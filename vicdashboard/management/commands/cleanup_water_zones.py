"""Reassign customers from obsolete zones to FOR ASSIGNMENT, then delete those zones."""

from django.core.management.base import BaseCommand
from django.db import transaction

from vicdashboard.models import WaterCustomer, WaterZone

OBSOLETE_ZONE_NAMES = (
    '1-2 BUHOK',
    'EXSON TAPAD',
    'HIGHWAY',
    'NEW',
    'NEXT MONTH',
    'TIGOY AREA',
    'WALA KAABOT ILA GRACE',
)

TARGET_ZONE_NAME = 'FOR ASSIGNMENT'


def normalize_zone_name(name):
    text = str(name or '').strip().upper()
    for ch in ('\u2013', '\u2014', '\u2212'):  # en-dash, em-dash, minus
        text = text.replace(ch, '-')
    return ' '.join(text.split())


class Command(BaseCommand):
    help = (
        'Reassign customers on obsolete water zones to FOR ASSIGNMENT, '
        'then delete those zones from the Zone list.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — no changes will be saved.'))

        zones_by_norm = {}
        for zone in WaterZone.objects.all():
            zones_by_norm.setdefault(normalize_zone_name(zone.name), []).append(zone)

        target_norm = normalize_zone_name(TARGET_ZONE_NAME)
        target_zones = zones_by_norm.get(target_norm, [])
        target_zone = target_zones[0] if target_zones else None
        target_created = False

        if target_zone is None:
            self.stdout.write(f'Target zone "{TARGET_ZONE_NAME}" does not exist yet.')
            if not dry_run:
                target_zone, target_created = WaterZone.objects.get_or_create(name=TARGET_ZONE_NAME)
                zones_by_norm[target_norm] = [target_zone]
            else:
                self.stdout.write('  (would create FOR ASSIGNMENT)')
        else:
            self.stdout.write(f'Target zone: {target_zone.name} (id={target_zone.pk})')

        found = 0
        missing = 0
        reassigned = 0
        deleted = 0

        obsolete_rows = []
        for name in OBSOLETE_ZONE_NAMES:
            matches = zones_by_norm.get(normalize_zone_name(name), [])
            if not matches:
                missing += 1
                self.stdout.write(self.style.WARNING(f'  missing: {name}'))
                continue
            found += 1
            for zone in matches:
                count = WaterCustomer.objects.filter(zone=zone).count()
                obsolete_rows.append((zone, count))
                self.stdout.write(f'  found: {zone.name} (id={zone.pk}) — {count} customer(s)')

        if dry_run:
            would_reassign = sum(count for _, count in obsolete_rows)
            self.stdout.write('')
            self.stdout.write(
                f'Summary (dry-run): found={found}, missing={missing}, '
                f'would_reassign={would_reassign}, would_delete={len(obsolete_rows)}, '
                f'would_create_target={target_zone is None}'
            )
            return

        with transaction.atomic():
            if target_zone is None:
                target_zone, target_created = WaterZone.objects.get_or_create(name=TARGET_ZONE_NAME)

            for zone, _count in obsolete_rows:
                if zone.pk == target_zone.pk:
                    continue
                moved = WaterCustomer.objects.filter(zone=zone).update(zone=target_zone)
                reassigned += moved
                zone.delete()
                deleted += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Summary: found={found}, missing={missing}, reassigned={reassigned}, '
            f'deleted={deleted}, target_created={target_created}'
        ))
