from apps.users.models import User
from apps.mails.models import ContactSubmission

print("User model DB table:", User._meta.db_table)
print("ContactSubmission model DB table:", ContactSubmission._meta.db_table)

responded_by_field = ContactSubmission._meta.get_field('responded_by')
print("ContactSubmission.responded_by references table:", responded_by_field.related_model._meta.db_table)
print("ContactSubmission.responded_by column name:", responded_by_field.column)
