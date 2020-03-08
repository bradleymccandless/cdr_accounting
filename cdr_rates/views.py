from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
import logging
import pymysql.cursors
import psycopg2
import math
import ast
import datetime
import itertools
import rrdtool
import time
import phonenumbers
from phonenumbers import geocoder
from cdr_rates.models import Rate, InternationalLowRate, InternationalHighRate, IndependentRate, LocalCallingArea, CachedRate

logger = logging.getLogger(__name__)
tollfree = ('888','877','866','855','844','833','822','800')

def kapi(request):
    import csv
    try:
        accountcode = request.GET.get('accountcode')
        month = request.GET.get('month')
        base_filename = settings.MEDIA_ROOT+'cdr-rates/'+month+'-'+accountcode
    except:
        logging.error('Malformed request. Please request an accountcode as an integer and a month string like 2018-05')
    try:
        rate_object = Rate.objects.get(accountcode=accountcode)
    except:
        logger.error('No rate entry for accountcode '+accountcode)
        return(JsonResponse({'call_charges':0,'call_overages':0}))
    try:
        cached_rate = CachedRate.objects.get(accountcode=rate_object,month=month)
        return(JsonResponse({'call_charges':cached_rate.call_charges,'call_overages':cached_rate.call_overages}))
    except:
        pass
    local_area = rate_object.local_calling_area
    pulse = rate_object.pulse
    channels = rate_object.channels
    inbound_rate = float(rate_object.inbound_rate)
    inbound_tollfree_rate = float(rate_object.inbound_tollfree_rate)
    outbound_rate = float(rate_object.outbound_rate)
    canadian_ld_rate = float(rate_object.canadian_ld_rate)
    united_states_ld_rate = float(rate_object.united_states_ld_rate)
    international_ld_rate = float(rate_object.international_ld_rate)

    default_ld_rate = min([canadian_ld_rate, united_states_ld_rate, international_ld_rate])
    default_international_rate = .5
    burst_rate = .03
    pic_rate = .0085
    inbound_minutes = 0
    outbound_minutes = 0
    pic_minutes = 0
    ld_minutes = 0
    international_low_rate_minutes = 0
    inbound_tollfree_minutes = 0
    independent_call_cost = 0
    international_call_cost = 0
    burst_call_cost = 0
    total_cost = 0
    call_discounts = 0
    concurrent_calls = {}

    international_low_rate_countries = (
        'United Kingdom', 'Ireland', 'Germany', 'Italy', 'France', 'Spain', 'Netherlands', 'Portugal', 
        'Luxembourg', 'Belgium', 'Austria', 'Denmark', 'Switzerland', 'China', 'Hong Kong', 
        'Australia', 'Malaysia', 'Singapore'
    )
    connection = pymysql.connect(
        host='10.2.0.50',
        user='*****',
        password='*****',
        db='*****',
        charset='utf8mb4'
    )
    #get all the pic numbers
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT number FROM pic_customer_number where account = '+str(accountcode)
            cursor.execute(sql)
            pics = list(itertools.chain(*cursor.fetchall()))
    finally:
        connection.close()
    for index,pic in enumerate(pics):
        row = pic.strip().lower().replace(' ', '').replace('-', '').replace('_', '')
        pics[index] = row
    pics = set(pics)
    #get all the npaas
    independent_npaas = IndependentRate.objects.all().values_list('e164_prefix')
    independent_npaas = [str(u[0]) for u in independent_npaas]
    international_low_rate_npaas = InternationalLowRate.objects.all().values_list('e164_prefix')
    international_low_rate_npaas = [str(u[0]) for u in international_low_rate_npaas]
    international_npaas = InternationalHighRate.objects.all().values_list('e164_prefix')
    international_npaas = [str(u[0]) for u in international_npaas]
    #this builds a set of cities we can call locally
    local_calling_cities = set()
    exchanges = []
    if len(local_area) > 4:
        local_calling_cities.add(local_area)
        try:
            exchanges = eval(LocalCallingArea.objects.get(locality=local_area).local_calling_areas)
        except:
            pass
        if len(exchanges) > 0:
            for exchange in exchanges:
                local_calling_cities.add(LocalCallingArea.objects.get(exchange=exchange).locality)
    else:
        local_calling_cities = {'Nowhere, XX'}

    #get the cdrs
    #now that CDRs are in django model we should use it instead of directly querying
    connection = psycopg2.connect(dbname='cdr-pusher', user='cdr-pusher', password='*****', host='localhost', port='9700')
    cursor = connection.cursor('CDRs from CDR-Pusher')
    sql = 'select caller_id_number,caller_id_name,destination_number,starting_date,duration,direction \
        from cdr_import where accountcode = \''+accountcode+'\' and hangup_cause_id = 16 and duration > 0 and \
        to_char(starting_date, \'YYYY-MM\') = \''+month+'\' order by starting_date;'
    cursor.execute(sql)
    file = open(base_filename+'.csv', 'w', encoding='utf-8')
    csvfile = csv.writer(file)
    csvfile.writerow(
        ['Day', 'Time', 'Duration', 'Call Cost', 'Call Class', 'Caller ID', 'Source Number', 'Destination Number',
        'Source Location', 'Destination Location', 'Destination Country']
    )
    for cdr in cursor:
        #some defaults
        direction = 'Outbound'
        if cdr[5] == 1:
            direction = 'Inbound'
        call_class = 'Local' # could be Incoming, Incoming Toll-free, Local, Local Network, Toll-free, Long Distance, Independent, Low Rate International, International, International Default Rate
        call_minutes = 0
        call_cost = 0
        call_minutes = math.ceil(int(cdr[4])/60)
        pulsed_call_minutes = math.ceil(int(cdr[4])/pulse) * (pulse/60)
        source = cdr[0].strip().lower().replace(' ', '').replace('-', '').replace('_', '').replace('+', '')
        destination = cdr[2].strip().lower().replace(' ', '').replace('-', '').replace('_', '').replace('+', '')
        destination_location = ''
        destination_country = ''
        #put minutes in the burst buckets
        for minute in range(call_minutes):
            current_minute = (cdr[3]+datetime.timedelta(minutes=minute)).strftime('%d:%H:%M')
            if current_minute in concurrent_calls:
                concurrent_calls[current_minute] += 1
            else:
                concurrent_calls[current_minute] = 1
        #format call source
        if len(source) > 6:
            try:
                source_number = phonenumbers.format_number(phonenumbers.parse(source, 'CA'), phonenumbers.PhoneNumberFormat.E164)
            except:
                if source.isdigit():
                    source_number = source
                else:
                    source_number = ''
        elif source.isdigit():
            source_number = source
        else:
            source_number = ''
        #locate call source
        if source_number[-10:-7] in tollfree:
            source_location = 'Toll-Free'
        else:
            try:
                source_location = geocoder.description_for_number(phonenumbers.parse(source_number, 'CA'), 'en')
            except:
                source_location = ''
        #format destination number
        if len(destination) > 6 and destination.isdigit():
            try:
                destination_number = phonenumbers.format_number(phonenumbers.parse(destination, 'CA'), phonenumbers.PhoneNumberFormat.E164)
            except:
                destination_number = destination
        if len(destination) < 7 and destination.isdigit():
            destination_number = destination
            if destination in ['211', '311', '511', '611', '811', '911']:
                call_class = 'Special Number'
            elif destination == '411':
                call_class = 'Directory Assistance'
            else:
                call_class = 'Extension'
        if not destination.isdigit():
            destination_number = ''
        if destination_number[-10:-7] in tollfree:
            destination_location = 'Toll-Free'
        else:
            try:
                destination_location = geocoder.description_for_number(phonenumbers.parse(destination_number, 'CA'), 'en')
            except:
                destination_location = ''
            try:
                destination_country = geocoder.country_name_for_number(phonenumbers.parse(destination_number, 'CA'), 'en')
            except:
                destination_country = ''
        #bill call
        if direction == 'Inbound':
            inbound_minutes += pulsed_call_minutes
            call_cost = pulsed_call_minutes * inbound_rate
            call_class = direction
            if destination_location == 'Toll-Free':
                call_class ='Inbound Toll-Free'
                inbound_tollfree_minutes += pulsed_call_minutes
                call_cost = call_minutes * inbound_tollfree_rate
        else: #call is outbound
            outbound_minutes += pulsed_call_minutes
            call_cost = pulsed_call_minutes * outbound_rate
            if call_class not in ['Local Network', 'Toll-Free'] and destination_location not in local_calling_cities:
                if destination_country == 'Canada':
                    call_class = 'Long Distance'
                    for npaa in sorted(independent_npaas, key=len, reverse=True):
                        if destination_number.startswith('+'+npaa):
                            call_class = 'Independent'
                            call_rate = float(IndependentRate.objects.get(e164_prefix=npaa).rate)
                            if call_rate <= canadian_ld_rate:
                                call_cost = canadian_ld_rate * call_minutes
                            else:
                                call_cost = call_rate * call_minutes
                            independent_call_cost += call_cost
                            destination_location = IndependentRate.objects.get(e164_prefix=npaa).destination
                            break
                    if call_class == 'Long Distance':
                        call_cost = canadian_ld_rate * pulsed_call_minutes
                        ld_minutes += pulsed_call_minutes
                elif destination_country == 'United States' or destination_number.startswith('+1'):
                    call_class = 'Long Distance'
                    for npaa in sorted(independent_npaas, key=len, reverse=True):
                        if destination_number.startswith('+'+npaa):
                            call_class = 'Independent'
                            call_rate = float(IndependentRate.objects.get(e164_prefix=npaa).rate)
                            if call_rate <= united_states_ld_rate:
                                call_cost = united_states_ld_rate * call_minutes
                            else:
                                call_cost = call_rate * call_minutes
                            independent_call_cost += call_cost
                            destination_location = IndependentRate.objects.get(e164_prefix=npaa).destination
                            break
                    if call_class == 'Long Distance':
                        call_cost = united_states_ld_rate * pulsed_call_minutes
                        ld_minutes += pulsed_call_minutes
                #check if it's an independant destination and charge int rates to the independant bucket. if not charge 2c to LD bucket
                elif destination_country in international_low_rate_countries:
                    call_class = 'International Low Rate' #check if it's a high rate internatioal dest and charge int rate to int bucket. if not charge 2c to int low rate bucket
                    for npaa in sorted(international_low_rate_npaas, key=len, reverse=True):
                        if destination_number.startswith('+'+npaa):
                            call_class = 'International'
                            call_rate = float(InternationalLowRate.objects.get(e164_prefix=npaa).rate)
                            if call_rate <= international_ld_rate:
                                call_cost = international_ld_rate * call_minutes
                            else:
                                call_cost = call_rate * call_minutes
                            international_call_cost += call_cost
                            destination_location = InternationalLowRate.objects.get(e164_prefix=npaa).destination
                            break
                    if call_class == 'International Low Rate':
                        call_cost = international_ld_rate * pulsed_call_minutes
                        international_low_rate_minutes += pulsed_call_minutes
                elif destination_country not in ['Canada', 'United States', '']:
                    call_class = 'International Default Rate' #check if it's has and internation amount and charge that. if not charge 50c.
                    for npaa in sorted(international_npaas, key=len, reverse=True):
                        if destination_number.startswith('+'+npaa):
                            call_class = 'International'
                            call_rate = float(InternationalHighRate.objects.get(e164_prefix=npaa).rate)
                            if call_rate <= international_ld_rate:
                                call_cost = international_ld_rate * call_minutes
                            else:
                                call_cost = call_rate * call_minutes
                            international_call_cost += call_cost
                            destination_location = InternationalHighRate.objects.get(e164_prefix=npaa).destination
                            break
                    if call_class == 'International Default Rate':
                        call_cost = default_international_rate * call_minutes
                        international_call_cost += call_cost
            for pic in pics:
                if pic in source_number:
                    pic_minutes += call_minutes
                    #there is some uncertainty here. our newest rate table says we stack 0.0085 on top of pic calls
                    #we'll have to clarify with dan or shannon. if we do just uncomment this
                    #call_cost += pic_rate * call_minutes
        if call_class in ['Local Network', 'Extension', 'Special Number']:
            call_cost = 0
        elif call_class == 'Directiory Assistance':
            call_cost = .5
        if '\"' in cdr[1]:
            caller_id_name = cdr[1].split('\"')[1]
        else:
            caller_id_name = cdr[1]
        csvfile.writerow(
            [cdr[3].strftime('%d'), cdr[3].strftime('%H:%M:%S'), cdr[4], round(call_cost,4), call_class, 
            caller_id_name, source_number, destination_number, source_location, destination_location, destination_country]
        )
        total_cost += call_cost
    connection.close()
    #find out if we used more channels than were paid for
    if channels != 0:
        epoch = str(int(time.mktime(time.strptime(month, '%Y-%m'))))
        start_date = str(int(epoch) - 1)
        rrdtool.create(base_filename+'.rrd', '-s60', 'DS:concurrent_calls:GAUGE:60:0:U', 'RRA:MAX:0:1:44640', '-b '+start_date)
        for minute in sorted(concurrent_calls):
            epoch = str(int(time.mktime(time.strptime(month+' '+minute, '%Y-%m %d:%H:%M'))))
            rrdtool.update(base_filename+'.rrd', epoch+":"+str(concurrent_calls[minute]))
            if concurrent_calls[minute] > channels:
                burst_call_cost += (concurrent_calls[minute] - channels) * burst_rate     
        end_date = epoch
        rrdtool.graph(
            base_filename+'.pdf', 
            '--width', '1920', 
            '--height', '400', 
            '--full-size-mode', 
            '--start', start_date,
            '--end', end_date,
            'DEF:calls='+base_filename+'.rrd:concurrent_calls:MAX',
            'CDEF:_calls=calls,UN,0,calls,IF',
            'AREA:_calls#8aacd2:    Total Concurrent Calls',
            '--imgformat', 'PDF',
            '--font', 'DEFAULT:11:\"Droid Sans\"',
            '--color', 'SHADEA#00000000',
            '--color', 'SHADEB#00000000',
            '--color', 'ARROW#00000000',
            '--color', 'BACK#00000000',
            '--color', 'CANVAS#00000000',
            '--lower-limit', '0',
            '--rigid',
            #'VDEF:average_calls=_calls,AVERAGE',
            #'GPRINT:average_calls:Average Concurrent Calls\: %.2lf'
        )
    #if two pass billing is enabled for this account run it
    if rate_object.two_pass_billing:
        def account_231(): #second-pass billing logic for account 231
            from shutil import move
            savings = 0
            with open(base_filename+'.csv', 'r') as f:
                reader = csv.reader(f)
                file = open(base_filename+'-0.csv', 'w', encoding='utf-8')
                csvfile = csv.writer(file)
                for row in reader:
                    if row[0] != 'Day':
                        if row[4] != 'Independent' and row[4] != 'International':
                            if int(row[2]) > 30:
                                pulsed_call_minutes = math.ceil(int(row[2])/30)*(30/60)
                                call_rate = float(row[3])/pulsed_call_minutes
                                pulsed_call_minutes = math.ceil(int(row[2])/6)*(6/60)
                                new_call_charge = round((call_rate * pulsed_call_minutes), 4)
                                savings += float(row[3]) - new_call_charge
                                row[3] = new_call_charge
                    csvfile.writerow(row)
            move(base_filename+'-0.csv', base_filename+'.csv')
            return(round(savings,2))
        def account_2681(): #second-pass billing logic for account 2681
            from shutil import move
            savings = 0
            with open(base_filename+'.csv', 'r') as f:
                reader = csv.reader(f)
                file = open(base_filename+'-0.csv', 'w', encoding='utf-8')
                csvfile = csv.writer(file)
                for row in reader:
                    if row[4] == 'Inbound Toll-Free':
                        pulsed_call_minutes = math.ceil(int(row[2])/30)*(30/60)
                        new_call_charge = round((.015 * pulsed_call_minutes), 4)
                        savings += float(row[3]) - new_call_charge
                        row[3] = new_call_charge
                    csvfile.writerow(row)
            move(base_filename+'-0.csv', base_filename+'.csv')
            return(round(savings,2))
        try:
            call_discounts = eval('account_'+accountcode+'()')
        except:
            logger.error('Second-pass rating failed for account '+accountcode+'!')
    #these should all become cost lines in silver.
    #echelon doesnt support extra fields so we just log them for now
    logger.info('Inbound minutes: %.1f' % inbound_minutes)
    logger.info('Outbound minutes: %.1f' % outbound_minutes)
    logger.info('Outbound PIC minutes: %.1f' % pic_minutes)
    logger.info('Long distance minutes: %.1f' % ld_minutes)
    logger.info('International low rate minutes: %.1f' % international_low_rate_minutes)
    logger.info('Toll-free incoming minutes: %.1f' % inbound_tollfree_minutes)
    if channels > 0:
        logger.info('Burst call charges: %.2f' % burst_call_cost)
    logger.info('Independent call charges: %.2f' % independent_call_cost)
    logger.info('International call charges: %.2f' % international_call_cost)
    logger.info('Total call charges: %.2f' % total_cost)
    if call_discounts > 0:
        logger.info('Total call discounts: %.2f' % call_discounts)
    if channels > 0:
        logger.info('Total call overages: %.2f' % burst_call_cost)
    cached_rate = CachedRate(accountcode=rate_object,month=month,call_charges=float('{0:.2f}'.format(total_cost-call_discounts)),call_overages=float('{0:.2f}'.format(burst_call_cost)))
    cached_rate.save()
    #give echelon what it wants. that pig
    return(JsonResponse({'call_charges':float('{0:.2f}'.format(total_cost-call_discounts)),'call_overages':float('{0:.2f}'.format(burst_call_cost))}))

def injest_rates(request):
    #this tool takes raw rate table data from a csv and puts it in to the proper tables.
    #run this tool whenever we get a new international/independent rate table.
    #it is very inefficient right now (sadface)
    #we should update it to accept a csv from a user! 
    import csv
    from cdr_rates.models import InternationalLowRate, InternationalHighRate, IndependentRate
    international_low_rate_cc = (
            '1144', '11353', '1149', '1139', '1133', '1134', '1131', '11351', 
            '11353', '1132', '1143', '1145', '1141', '1186', '11852', 
            '1161', '1160', '1165'
        )
    sql = 'delete from expensive_destinations;\n'
    with open('cdr_rates/resources/rates.csv', 'r') as f:
        rates = list(csv.reader(f))
        for index,rate in enumerate(rates):
            if index != 0:
                if not rate[0].startswith('*') and not rate[0].startswith(tollfree) and 'E' not in rate[0]:
                    if float(rate[2]) > 0:
                        if rate[0].startswith('11'):
                            e164_npaa = '+'+rate[0][2:]
                            if rate[0].startswith(international_low_rate_cc):
                                try:
                                    InternationalLowRate.objects.get(e164_prefix=e164_npaa[1:])
                                    if float(rate[2]) > float(InternationalLowRate.objects.get(e164_prefix=e164_npaa[1:]).rate):
                                        insert = InternationalLowRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                        insert.save()
                                except:
                                    insert = InternationalLowRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                    insert.save()
                            else:
                                try:
                                    InternationalHighRate.objects.get(e164_prefix=e164_npaa[1:])
                                    if float(rate[2]) > float(InternationalHighRate.objects.get(e164_prefix=e164_npaa[1:]).rate):
                                        insert = InternationalHighRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                        insert.save()
                                except:
                                    insert = InternationalHighRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                    insert.save() 
                        else:
                            if rate[0].startswith('1'):
                                e164_npaa = '+'+rate[0]
                            else:
                                e164_npaa = '+1'+rate[0]
                            try:
                                IndependentRate.objects.get(e164_prefix=e164_npaa[1:])
                                if float(rate[2]) > float(IndependentRate.objects.get(e164_prefix=e164_npaa[1:]).rate):
                                    insert = IndependentRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                    insert.save()
                            except:
                                insert = IndependentRate(e164_prefix=e164_npaa[1:], destination=rate[1].strip(), rate=rate[2])
                                insert.save()
                    if float(rate[2]) > 0.02:
                        if rate[0].startswith('11'):
                            prefix = rate[0][2:]
                        else:
                            if rate[0].startswith('1'):
                                prefix = rate[0]
                            else:
                                prefix = '1'+rate[0]
                        sql += "insert into expensive_destinations (e164_prefix,destination,rate) values ("+prefix+", '"+rate[1].strip()+"', "+rate[2]+");\n"
    #really should make this a model and use django orm
    connection = psycopg2.connect(dbname='cdr-pusher', user='cdr-pusher', password='*****', host='localhost', port='9700')
    cursor = connection.cursor()
    cursor.execute(sql)
    connection.commit()
    connection.close()
    return(JsonResponse({'Import Complete':True}))
