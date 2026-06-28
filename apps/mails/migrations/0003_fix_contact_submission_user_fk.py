from django.db import migrations


def fix_contact_submission_user_fk(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_key_list(contact_submissions)')
            fks = cursor.fetchall()
            if not any(fk[2] == 'users_user' for fk in fks):
                return

            cursor.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name='contact_submissions'"
            )
            indexes = [
                (name, sql)
                for name, sql in cursor.fetchall()
                if sql and not name.startswith('sqlite_')
            ]

            cursor.execute('PRAGMA foreign_keys=OFF')
            cursor.execute(
                """
                CREATE TABLE contact_submissions_new (
                    id char(32) NOT NULL PRIMARY KEY,
                    name varchar(255) NOT NULL,
                    email varchar(254) NOT NULL,
                    message text NOT NULL,
                    status varchar(20) NOT NULL,
                    ip_address char(39) NULL,
                    user_agent text NULL,
                    admin_notes text NULL,
                    responded_at datetime NULL,
                    created_at datetime NOT NULL,
                    updated_at datetime NOT NULL,
                    responded_by_id char(32) NULL REFERENCES users(id)
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO contact_submissions_new (
                    id, name, email, message, status, ip_address, user_agent,
                    admin_notes, responded_at, created_at, updated_at, responded_by_id
                )
                SELECT
                    id, name, email, message, status, ip_address, user_agent,
                    admin_notes, responded_at, created_at, updated_at, responded_by_id
                FROM contact_submissions
                """
            )
            cursor.execute('DROP TABLE contact_submissions')
            cursor.execute(
                'ALTER TABLE contact_submissions_new RENAME TO contact_submissions'
            )
            for _name, sql in indexes:
                cursor.execute(sql)
            cursor.execute('PRAGMA foreign_keys=ON')
            return

        if connection.vendor == 'postgresql':
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'contact_submissions'
                """
            )
            if not cursor.fetchone():
                return

            # Join pg_catalog — do not cast missing relations to regclass (crashes migrate).
            cursor.execute(
                """
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class rel ON rel.oid = c.conrelid
                JOIN pg_class frel ON frel.oid = c.confrelid
                JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                WHERE nsp.nspname = 'public'
                  AND rel.relname = 'contact_submissions'
                  AND c.contype = 'f'
                  AND frel.relname = 'users_user'
                """
            )
            constraints = cursor.fetchall()
            if not constraints:
                return

            for (conname,) in constraints:
                cursor.execute(
                    f'ALTER TABLE contact_submissions DROP CONSTRAINT "{conname}"'
                )
            cursor.execute(
                """
                ALTER TABLE contact_submissions
                ADD CONSTRAINT contact_submissions_responded_by_id_fkey
                FOREIGN KEY (responded_by_id) REFERENCES users(id)
                DEFERRABLE INITIALLY DEFERRED
                """
            )
            return


class Migration(migrations.Migration):

    dependencies = [
        ('mails', '0002_contactsubmission'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            fix_contact_submission_user_fk,
            migrations.RunPython.noop,
        ),
    ]
