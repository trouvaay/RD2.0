import uuid

from django.conf import settings
from django.contrib.auth.models import User as BaseUser
from django.db import models
from django.db.models import Q
from django.utils import timezone
from localflavor.us.models import PhoneNumberField

from cloudinary.models import CloudinaryField


# ----------------------------------------------------
# Mixins
# ----------------------------------------------------
class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(blank=False, null=False)
    updated_at = models.DateTimeField(blank=False, null=False)

    def save(self, *args, **kwargs):
        """Sets/updates created_at and updated_at timestamps"""

        right_now = timezone.now()
        if(not self.id):
            self.created_at = right_now
        self.updated_at = right_now
        super(TimestampedModel, self).save(*args, **kwargs)

    class Meta:
        abstract = True

class AbstractImageModel(models.Model):
    """Abstract image model for ProductIMage and RetailerIMage models.
    Uses Cloudinary for image rendering
    """
    #main image will be primary/1st displayed to user
    is_main = models.BooleanField(default=False)
    image = CloudinaryField('image')
    
    class Meta:
        abstract = True


# ----------------------------------------------------
# Choices
# ----------------------------------------------------
class OrgType(object):
    """This class maintains a list of all Org. types"""
    INDIVIDUAL = 'INDIVIDUAL'
    CORPORATION = 'CORPORATION'

ORG_TYPES = (
    (OrgType.INDIVIDUAL, 'Individual'),
    (OrgType.CORPORATION, 'Corporation'),
)


class DiscountType(object):
    """This class maintains a list of all Discount types"""
    RETAILER_SPECIFIC = 'RETAILER_SPECIFIC'
    GENERAL = 'GENERAL'

DISCOUNT_TYPES = (
    (DiscountType.RETAILER_SPECIFIC, 'Retailer-specific promo'),
    (DiscountType.GENERAL, 'General discount'),
)

class OrderType(object):
    """This class maintains a list of all order types"""
    PURCHASE = 'PURCHASE'
    OFFER = 'OFFER'

ORDER_TYPES = (
    (OrderType.PURCHASE, 'Purchase'),
    (OrderType.OFFER, 'Offer'),
)

# ----------------------------------------------------
# Models
# ----------------------------------------------------


class User(UUIDModel, BaseUser):
    """Custom user model to allow login using email.
    We will still have a username field but it is not
    goint to be used anywhere. The value of username
    will be email hash to guarantee that it is always unique
    """
    pass


class PostalAddress(UUIDModel, TimestampedModel):
    street = models.CharField(max_length=50)
    street2 = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=20)
    state = models.CharField(max_length=2)  # TODO: needs list of choices here
    zipcd = models.IntegerField()
    phone = models.CharField(max_length=120)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    neighborhood = models.CharField(max_length=80)  # TODO: needs list of choices here


class Profile(models.Model):
    """This is the place where we add any fields when we need a new user property"""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, blank=False, null=False, related_name='profile')
    phone = PhoneNumberField(blank=True, null=False, default='')
    is_merchant = models.BooleanField(blank=False, null=False, default=False)
    account_balance = models.DecimalField(help_text="Positive value means credit to the user, negative means user ows to us")
    shipping_address = models.ForeignKey(blank=True, null=True, default=True)


class Shipper(models.Model):
    name = models.CharField(max_length=100, unique=True)
    phone = PhoneNumberField(max_length=12)
    email = models.CharField(max_length=255, unique=True)


class Retailer(UUIDModel):
    legal_name = models.CharField(max_length=255)
    short_name = models.CharField(max_length=100)
    organization_type = models.CharField(max_length=20, choices=ORG_TYPES)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, limit_choices_to=Q(profile__is_merchant=True), null=True, blank=True)
    address = models.ForeignKey(PostalAddress, blank=True, null=True, default=None)
    website = models.URLField(null=True, blank=True)
    commision_fee = models.DecimalField(blank=False, null=False, max_digits=8, decimal_places=2)
    transaction_fee = models.DecimalField(blank=False, null=False, max_digits=8, decimal_places=2)
    order_prefix = models.CharField(max_length=4, unique=True, blank=False, null=False, help_text='This will be pre-pended to all orders from this retailer')

class RetailerImage(AbstractImageModel):
    retailer = models.ForeignKey(Retailer, related_name='images')
    is_logo = models.BooleanField(default=False)


class Store(models.Model):
    retailer = models.ForeignKey(Retailer, related_name='stores')
    store_num = models.CharField(max_length=10, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    shippers = models.ManyToManyField(Shipper, null=True, blank=True, related_name='stores')
    is_featured = models.BooleanField(default=False)
    has_returns = models.BooleanField(default=False)


class Discount(models.Model):
    
    name = models.CharField(max_length=100, blank=False, null=False, help_text='e.g. Get $10 off your $50 order')
    short_terms = models.TextField(max_length=1000, blank=True, null=False, defult='', help_text='This is a short vertion of the terms that we can show to the user e.g. on a front page where they might actually read it.')
    terms = models.TextField(max_length=10000, blank=True, null=False, default='', help_text='This is the "fine print", explaining in every details the terms of the promotion')

    # having a special field would allow us to figure out
    # how each 'kind' of offer should be handled
    discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPES, blank=False, null=False, db_index=True, help_text='This field determines how offer is applied: e.g. Retailer-specific discounts are only for the goods sold by that retailer')
    retailer = models.ForeignKey(Retailer, blank=True, null=True, default=None, related_name='discounts')

    # The following fields are used to determine whether or not this discount is valid. The most imporant one
    # is "is_active" which takes precedence over any other fields when determining whether or not the offer is valid
    # e.g. start/end time, uses_per_user, or uses_total would only have meaning the offer is active
    # making default=False, so that we have to explicitly enable it
    is_active = models.BooleanField(blank=False, null=False, default=False, help_text='This is On/Off switch for the offer')
    start_time = models.DateTimeField(blank=True, null=True, default=None, help_text='When offer becomes available')
    end_time = models.DateTimeField(blank=True, null=True, default=None, help_text='When offer expires')
    uses_per_user = models.IntegerField(blank=False, null=False, help_text='Positive number - how many times this offer can be used per user, -1 - unlimited')
    uses_total = models.IntegerField(blank=False, null=False, help_text='Positive number - total number of times this offer can be used, -1 - unlimited')

    # codes must be unique, but they are also optional
    # we will handle the uniqueness in the 'save' method
    # because django can't handle unique and optinally empty fields
    # the way one would expect. I've ran into this long time ago,
    # but the issue still remains to this day see my stackoverflow question for details
    # http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django
    code = models.CharField(max_length=100, blank=True, default='', db_index=True, help_text='Code for the promotion. Codes are case insensitive, e.g. PROMO2015 and Promo2015 is the same thing, so cannot create two different codes like that.')

    # The following fields determine the actual value of the discount
    # Either fixed_amount_off or percent_off must be set and be non-zero
    # we will handle this constraint in the save() method
    fixed_amount_off = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=None, help_text='e.g. 20 means $20 off')
    fixed_amount_off_minimum_order = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=None, help_text='Order minimum that is required (if any) to get this discount. 0 means there is not minimum. This is applicable only when fixed_amount_off is set')
    percent_off = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=None, help_text='Expressed as percentage, e.g. 10 means 10% off')
    percent_off_limit = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=None, help_text='Limits the maximum dollar value of the Percent discount off. This is applicable only when percent_off is set')



def generate_order_number(order):
    """Generates new order number in the following format:
    
    <RETAILER PREFIX><NUMERIC PART>
    
    RETAILER PREFIX - string containing letters, comes from order.product.retailer.order_prefix
    NUMERIC PART - number that along with retailer prefix makes the order unique
    """
    pass

class Order(TimestampedModel):
    order_number = models.CharField(primary_key=True, max_lendth=20, blank=False, null=False, default=generate_order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=False, null=False, related_name='user_orders')
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, blank=False, null=False, db_index=True)
    address = models.ForeignKey(PostalAddress)
    subtotal = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text='Total price of all items before discounts, shipping  and taxes')
    taxes = models.DecimalField(max_digits=8, decimal_places=2, blank=None, null=None, default=0.00, help_text="Taxes in dollars")
    total_transaction_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text='Total purchase price the user paid including promotions and taxes')


class OrderItem(TimestampedModel):
    order = models.ForeignKey(Order, related_name='order_items')
    quantity = models.PositiveIntegerField(blank=False, null=False)
    product = models.ForeignKey('Product', blank=False, null=False, related_name='product_orders')
    original_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text='Price of the product at the time of purchase')


class Offer(TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=False, null=False, related_name='user_orders')
    product = models.ForeignKey('Product', blank=False, null=False, related_name='product_orders')
    address = models.ForeignKey(PostalAddress)
    offer_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text='Price offered by user for the product')
    taxes = models.DecimalField(max_digits=8, decimal_places=2, blank=None, null=None, default=0.00, help_text="Taxes in dollars")
    total_transaction_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00, help_text='Total purchase price including taxes')
    is_captured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expiration_timestamp = models.DateTimeField(blank=False, null=False, help_text='When this offer expires')


class DiscountRedemption(models.Model):
    authuser = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='user_redemptions')
    discount = models.ForeignKey(Discount, blank=False, null=False, related_name='discount_redemptions')
    order = models.ForeignKey(Order, blank=False, null=False, related_name='order_discount_redemptions')
    timestamp = models.DateTimeField(blank=False, null=False, help_text='When this was redeemed')
    total_before_discount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=None, help_text="Total dollar amount before applying any promotinal discounts to the order")
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=None, help_text="Discount dollar amount")


# ----------------------------------------------------
# Product-related models
# ----------------------------------------------------
class Segment(models.Model):
    select = models.CharField(unique=True, max_length=55, default='new', null=True, blank=True)


class Style(models.Model):
    select = models.CharField(unique=True, max_length=55, default='modern', null=True, blank=True)


class FurnitureType(models.Model):
    select = models.CharField(unique=True, max_length=55, default='seating', null=True, blank=True)
    is_furniture = models.BooleanField(default=True)


class ValueTier(models.Model):
    select = models.CharField(unique=True, max_length=55, default='mid', null=True, blank=True)


class Category(models.Model):
    select = models.CharField(unique=True, max_length=55, default='living', null=True, blank=True)


class Subcategory(models.Model):
    select = models.CharField(unique=True, max_length=55, default='bar', null=True, blank=True)
    trial_product = models.BooleanField(default=False)
    shipping_charge = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, choices=[(5.00, 5.00), (20.00, 20.00), (50.00, 50.00)])


class Color(models.Model):
    select = models.CharField(unique=True, max_length=55, default='blue', null=True, blank=True)


class Material(models.Model):
    select = models.CharField(unique=True, max_length=55, default='leather', null=True, blank=True)


class Product(UUIDModel, TimestampedModel):

    manufacturer = models.CharField(max_length=100, null=True, blank=True)
    manufacturer_sku = models.CharField(max_length=100, null=True, blank=True)
    upc = models.CharField(max_length=12, null=True, blank=True)

    short_name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, max_length=255)
    original_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    current_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    description = models.TextField(null=True, blank=True)
    store = models.ForeignKey(Store)
    units = models.IntegerField(default=1)
    url = models.URLField(null=True, blank=True, max_length=255)
    minimum_offer_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, default=None)

    # shipping properties
    shipping_width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    shipping_depth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    shipping_height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # Dimensions & Attributes
    width = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    depth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    seat_height = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    diameter = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    bed_size = models.CharField(max_length=50, null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    color = models.ManyToManyField(Color, null=True, blank=True)
    color_description = models.CharField(max_length=100, null=True, blank=True)
    material = models.ManyToManyField(Material, null=True, blank=True)
    material_description = models.CharField(max_length=255, null=True, blank=True)
    tags = models.TextField(null=True, blank=True)  # list of tag words
    is_custom = models.BooleanField(default=False)
    is_floor_model = models.BooleanField(default=False)

    # Categorization
    segment = models.ManyToManyField(Segment, null=True, blank=True)
    style = models.ManyToManyField(Style, null=True, blank=True, verbose_name='style')
    furnituretype = models.ManyToManyField(FurnitureType, null=True, blank=True)
    category = models.ManyToManyField(Category, null=True, blank=True)
    subcategory = models.ManyToManyField(Subcategory, null=True, blank=True)  # required for has_trial

    # Availability
    added_date = models.DateTimeField(auto_now_add=True)
    pub_date = models.DateTimeField(null=True, blank=True)
    is_sold = models.BooleanField(default=False)
    is_reserved = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_recent = models.BooleanField(default=True)
    hours_left = models.IntegerField(default=settings.SHELF_LIFE, null=True, blank=True)
    is_landing = models.BooleanField(default=False)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    md5_order = models.CharField(max_length=32, null=True, blank=True)
    click_count = models.IntegerField(blank=False, null=False, default=0)
    display_score = models.IntegerField(blank=False, null=False, default=0)
    the_hunt = models.BooleanField(default=False)
