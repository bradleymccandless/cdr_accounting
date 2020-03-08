from django.db import models
from django.contrib.postgres.fields import JSONField

class Rate(models.Model):
    accountcode = models.PositiveIntegerField('Account Code',primary_key=True,blank=False)
    local_calling_area = models.CharField('Local Calling Area',blank=True,max_length=128)
    pulse = models.PositiveSmallIntegerField('Pulse',default=60)
    channels = models.PositiveSmallIntegerField('Channels',default=0)
    inbound_rate = models.DecimalField('Inbound Calling Rate',default=0.02,decimal_places=4,max_digits=4)
    inbound_tollfree_rate = models.DecimalField('Inbound Tollfree Calling Rate',default=0.03,decimal_places=4,max_digits=4) 
    outbound_rate = models.DecimalField('Outbound Calling Rate',default=0.02,decimal_places=4,max_digits=4)
    canadian_ld_rate = models.DecimalField('Canadian Long Distance Rate',default=0.02,decimal_places=4,max_digits=4) 
    united_states_ld_rate = models.DecimalField('American Long Distance Rate',default=0.02,decimal_places=4,max_digits=4) 
    international_ld_rate = models.DecimalField('International Long Distance Rate',default=0.02,decimal_places=4,max_digits=4) 
    two_pass_billing = models.BooleanField('Do we need to run two-pass billing?',default=False)


cdr_direction_choices = ((2, 'Outgoing'),(1,'Incoming'))
cdr_hangup_cause_ids = (
    (0,'Unspecified'),(1,'Unallocated Number'),(2,'No Route To Specified Transit Network'),(3,'No Route To Destination'),
    (6,'Channel Unacceptable'),(7,'Call Awarded, Being Delivered In An Established Channel'),(16,'Completed'),(17,'User Busy'),
    (18,'No User Response'),(19,'No Answer'),(20,'Subscriber Absent'),(21, 'Call Rejected'),(22,'Number Changed'),
    (23,'Redirected to New Destination'),(25,'Exchange Routing Error'),(27,'Destination Out of Order'),(28,'Invalid Number Format'),
    (29,'Facilities Rejected'),(30,'Response to Status Inquiry'),(31,'Completed, Unspecified'),(34,'Circuit Congestion'),
    (38,'Network Out of Order'),(41,'Temporary Failure')
)
class CDR(models.Model):
    id = models.AutoField(primary_key=True)
    switch = models.CharField(max_length=80)
    cdr_source_type = models.IntegerField(blank=True,null=True,editable=False)
    callid = models.CharField(max_length=80,editable=False)
    caller_id_number = models.CharField(max_length=80,editable=False,verbose_name='Caller ID Number')
    caller_id_name = models.CharField(max_length=80,verbose_name='Caller ID')
    destination_number = models.CharField(max_length=80,verbose_name='Dialed Number')
    dialcode = models.CharField(max_length=10,blank=True,editable=False)
    state = models.CharField(max_length=5,blank=True,editable=False)
    channel = models.CharField(max_length=80,blank=True)
    starting_date = models.DateTimeField(verbose_name='Date and Time')
    duration = models.IntegerField()
    billsec = models.IntegerField(editable=False)
    progresssec = models.IntegerField(blank=True,null=True,editable=False)
    answersec = models.IntegerField(blank=True,null=True,editable=False)
    waitsec = models.IntegerField(blank=True,null=True,editable=False)
    hangup_cause_id = models.IntegerField(blank=True,null=True,choices=cdr_hangup_cause_ids,verbose_name='Hangup Cause')
    hangup_cause = models.CharField(max_length=80,blank=True,editable=False)
    direction = models.IntegerField(blank=True,null=True,choices=cdr_direction_choices)
    country_code = models.CharField(max_length=3,blank=True,editable=False)
    accountcode = models.CharField(max_length=40,blank=True,verbose_name='Account Code')
    buy_rate = models.DecimalField(max_digits=10,decimal_places=5,blank=True,null=True,editable=False)
    buy_cost = models.DecimalField(max_digits=12,decimal_places=5,blank=True,null=True,editable=False)
    sell_rate = models.DecimalField(max_digits=10,decimal_places=5,blank=True,null=True,editable=False)
    sell_cost = models.DecimalField(max_digits=12,decimal_places=5,blank=True,null=True,editable=False)
    imported = models.BooleanField(default=False,editable=False)
    extradata = JSONField(blank=True)
    class Meta:
        db_table = 'cdr_import'
        ordering = ['-starting_date']
        verbose_name = 'CDR'
        verbose_name_plural = 'CDRs'

class InternationalLowRate(models.Model):
    e164_prefix = models.BigIntegerField('E.164-formatted prefixes without leading \"+\".',blank=False,primary_key=True)
    destination = models.CharField('The call destination.',blank=False,max_length=96)
    rate = models.DecimalField('Call rate.',decimal_places=4,max_digits=6)

class InternationalHighRate(models.Model):
    e164_prefix = models.BigIntegerField('E.164-formatted prefixes without leading \"+\".',blank=False,primary_key=True)
    destination = models.CharField('The call destination.',blank=False,max_length=96)
    rate = models.DecimalField('Call rate.',decimal_places=4,max_digits=6)

class IndependentRate(models.Model):
    e164_prefix = models.BigIntegerField('E.164-formatted prefixes without leading \"+\".',blank=False,primary_key=True)
    destination = models.CharField('The call destination.',blank=False,max_length=96)
    rate = models.DecimalField('Call rate.',decimal_places=4,max_digits=6)

class LocalCallingArea(models.Model):
    exchange = models.CharField('The six-character exchange identifier.',blank=False,primary_key=True,max_length=6)
    locality = models.CharField('The exchange location.',blank=False,max_length=96)
    local_calling_areas = models.CharField('An array of all the local calling areas by exchange identifier.',default='',blank=True,max_length=1024)

class CachedRate(models.Model):
    accountcode = models.OneToOneField(Rate,primary_key=True,on_delete=models.CASCADE)
    month = models.CharField('The rated month.',blank=False,max_length=7)
    call_charges = models.DecimalField('Call Charges',default=0,decimal_places=2,max_digits=7)
    call_overages = models.DecimalField('Call Charges',default=0,decimal_places=2,max_digits=7)