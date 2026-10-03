from .models import Tag 
from .defaults import DEFAULT_TAGS
def create_default_tags_for_user(user):
    for name,category in DEFAULT_TAGS:
        Tag.objects.get_or_create(user=user,
                                  name=name,
                                  defaults={"category":category,
                                            "is_system":True}
                                            )