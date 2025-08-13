from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from App.models import Project, UserProfile, Mentor

class Command(BaseCommand):
    help = 'Setup initial data for defect tracker'
    def handle(self, *args, **options):
        project1, created = Project.objects.get_or_create(
            name="Web Application",
            defaults={
                'description': 'Main web application project',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created project: {project1.name}')
        project2, created = Project.objects.get_or_create(
            name="Mobile App",
            defaults={
                'description': 'Mobile application project',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created project: {project2.name}')
        project3, created = Project.objects.get_or_create(
            name="API Backend",
            defaults={
                'description': 'Backend API services',
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'Created project: {project3.name}')
        mentor_user, created = User.objects.get_or_create(
            username='mentor1',
            defaults={
                'email': 'mentor1@example.com',
                'is_active': True
            }
        )
        if created:
            mentor_user.set_password('mentor123')
            mentor_user.save()
            self.stdout.write(f'Created mentor user: {mentor_user.username}')
        mentor, created = Mentor.objects.get_or_create(
            user=mentor_user,
            defaults={
                'mentor_username': 'mentor1',
                'is_active': True
            }
        )
        if created:
            mentor.projects.add(project1, project2)
            self.stdout.write(f'Created mentor: {mentor.mentor_username}')
        self.stdout.write(
            self.style.SUCCESS('Successfully set up initial data!')
        )
        self.stdout.write('Sample login credentials:')
        self.stdout.write('Mentor - Username: mentor1, Password: mentor123')
        self.stdout.write('Available projects: Web Application, Mobile App, API Backend')