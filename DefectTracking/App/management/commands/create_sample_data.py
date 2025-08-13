from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from defects.models import Project, Mentor

class Command(BaseCommand):
    help = 'Create sample projects and mentors'
    
    def handle(self, *args, **options):
        # Create sample projects
        projects = [
            'E-commerce Platform',
            'Mobile Banking App',
            'CRM System',
            'Inventory Management',
            'HR Portal'
        ]
        
        for project_name in projects:
            project, created = Project.objects.get_or_create(
                name=project_name,
                defaults={'description': f'Sample project: {project_name}'}
            )
            if created:
                self.stdout.write(f'Created project: {project_name}')
        
        # Create sample mentor
        mentor_user, created = User.objects.get_or_create(
            username='mentor1',
            defaults={
                'email': 'mentor@nammaqa.com',
                'first_name': 'John',
                'last_name': 'Mentor'
            }
        )
        
        if created:
            mentor_user.set_password('mentor123')
            mentor_user.save()
            
            mentor, _ = Mentor.objects.get_or_create(
                user=mentor_user,
                mentor_username='mentor1'
            )
            mentor.projects.set(Project.objects.all())
            
            self.stdout.write('Created sample mentor: mentor1 (password: mentor123)')
        
        self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))
