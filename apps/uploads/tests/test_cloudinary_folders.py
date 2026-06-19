from django.test import TestCase, override_settings

from apps.uploads.cloudinary_folders import (
    cloudinary_folder,
    cloudinary_task_attachments_folder,
    cloudinary_users_profiles_folder,
    get_cloudinary_root,
    resolve_cloudinary_folder,
)


class CloudinaryFoldersTests(TestCase):
    @override_settings(CLOUDINARY_DEFAULT_FOLDER='Sajilowork')
    def test_root_folder(self):
        self.assertEqual(get_cloudinary_root(), 'Sajilowork')

    @override_settings(CLOUDINARY_DEFAULT_FOLDER='Sajilowork')
    def test_nested_user_profile_folder(self):
        self.assertEqual(cloudinary_users_profiles_folder(), 'Sajilowork/Users/Profiles')

    @override_settings(CLOUDINARY_DEFAULT_FOLDER='Sajilowork')
    def test_task_attachment_folder(self):
        self.assertEqual(
            cloudinary_task_attachments_folder('abc-123'),
            'Sajilowork/Tasks/abc-123',
        )

    @override_settings(CLOUDINARY_DEFAULT_FOLDER='Sajilowork')
    def test_resolve_shorthand_folder(self):
        self.assertEqual(resolve_cloudinary_folder('Users/Profiles'), 'Sajilowork/Users/Profiles')

    @override_settings(CLOUDINARY_DEFAULT_FOLDER='Sajilowork')
    def test_resolve_absolute_folder(self):
        self.assertEqual(
            resolve_cloudinary_folder('Sajilowork/Tasks/task-1'),
            'Sajilowork/Tasks/task-1',
        )

    @override_settings(CLOUDINARY_DEFAULT_FOLDER='CustomRoot')
    def test_custom_root(self):
        self.assertEqual(cloudinary_folder('Users'), 'CustomRoot/Users')
