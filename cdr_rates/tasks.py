from __future__ import absolute_import, unicode_literals
from celery import Celery
from celery.utils.log import get_task_logger
app = Celery()
logger = get_task_logger(__name__)

@app.task
def get_exchanges():
    #this tool syncs exchange info with http://localcallingguide.com
    #dont run this more than necessary since it puts a load on Ray Chow's servers
    #check for updates here http://localcallingguide.com/updates.php
    #last updated 2018-05
    import requests
    import bs4
    response = requests.get('http://localcallingguide.com/lca_listregion.php')
    soup = bs4.BeautifulSoup(response.content, "html5lib")
    exchanges = set()
    for data_label in soup.select('td[data-label="Region"] a'):
        region = str(data_label).split('.php')[1].split('\"')[0]
        region_xml = requests.get('http://localcallingguide.com/xmlrc.php'+region)
        region_soup = bs4.BeautifulSoup(region_xml.content, "html5lib")
        for rc_data in region_soup.select('rcdata'):
            exchanges.add(rc_data.select('exch')[0].get_text())
    for exchange in exchanges:
        try:
            LocalCallingArea.objects.get(exchange=exchange)
        except:
            exchange_xml = requests.get('http://localcallingguide.com/xmllocalexch.php?rconly=1&exch='+exchange)
            exchange_soup = bs4.BeautifulSoup(exchange_xml.content, "html5lib")
            local_exchanges = set()
            if len(exchange_soup.select('prefix')) > 0:
                print(exchange)
                for local_exchange in exchange_soup.select('prefix'):
                    if local_exchange.select('exch')[0].get_text() == exchange:
                        exchange_entry = LocalCallingArea(exchange=exchange,locality=local_exchange.select('rc')[0].get_text()+', '+local_exchange.select('region')[0].get_text())
                    else:
                        local_exchanges.update(local_exchange.select('exch')[0])
                if len(local_exchanges) > 0:
                    exchange_entry.local_calling_areas = str(sorted(list(local_exchanges)))
                exchange_entry.save()

@app.task
def accountcoder(create_tickets=False):
    import pymysql.cursors, json, requests, math
    from django.db import transaction
    from cdr_rates.models import CDR
    def strip_it(string_to_strip):
        return(string_to_strip.strip().lower().replace(' ', '').replace('-', '').replace('_', '').replace('+', ''))
    connection = pymysql.connect(
        host='10.2.0.50',
        user='*****',
        password='*****',
        db='*****',
        charset='utf8mb4'
    )
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT outbound_trunk, customer FROM user_trunks'
            cursor.execute(sql)
            trunks = list(cursor.fetchall())
            sql = 'SELECT did, account FROM did'
            cursor.execute(sql)
            dids = list(cursor.fetchall())
            sql = 'SELECT number, account FROM pic_customer_number'
            cursor.execute(sql)
            dids += list(cursor.fetchall())
    finally:
        connection.close()
    for index,trunk in enumerate(trunks):
        row = (strip_it(trunk[0]), trunk[1])
        trunks[index] = row
    trunks = set(trunks)
    for index,did in enumerate(dids):
        row = (strip_it(did[0]), did[1])
        dids[index] = row
    dids = set(dids)
    lost_incoming_calls_by_trunk = {}
    lost_outgoing_calls_by_trunk = {}
    lost_calls_by_did = {}
    for cdr in CDR.objects.all().filter(accountcode=''):
        accountcode = 0
        estimated_call_cost = math.ceil(cdr.duration/60)*.02
        if cdr.direction == 1: #inbound
            call_trunk = cdr.extradata['dstchannel']
            if 'SIP\\' in cdr.extradata['dstchannel']:
                call_trunk = call_trunk.split('SIP\\',1)[-1]
            if 'SIP/' in cdr.extradata['dstchannel']:
                call_trunk = call_trunk.split('SIP/',1)[-1]
            if '-' in cdr.extradata['dstchannel']:
                call_trunk = call_trunk[::-1].split('-',1)[-1][::-1]
            call_trunk = strip_it(call_trunk)
            did = strip_it(cdr.destination_number)
            trunk_accountcode = [element for element in trunks if element[0] in call_trunk]
            did_accountcode = [element for element in dids if element[0] in did]
        elif cdr.direction == 2: #outbound
            call_trunk = cdr.channel
            if 'SIP\\' in cdr.channel:
                call_trunk = call_trunk.split('SIP\\',1)[-1]
            if 'SIP/' in cdr.channel:
                call_trunk = call_trunk.split('SIP/',1)[-1]
            if '-' in cdr.channel:
                call_trunk = call_trunk[::-1].split('-',1)[-1][::-1]
            call_trunk = strip_it(call_trunk)
            did = strip_it(cdr.caller_id_number)
            trunk_accountcode = [element for element in trunks if element[0] in call_trunk]
            did_accountcode = [element for element in dids if element[0] in did]
            if trunk_accountcode:
                if call_trunk in lost_outgoing_calls_by_trunk:
                    lost_outgoing_calls_by_trunk[call_trunk] += estimated_call_cost
                else:
                    lost_outgoing_calls_by_trunk[call_trunk] = estimated_call_cost
        if trunk_accountcode:
            accountcode = trunk_accountcode[0][1]
        if did_accountcode:
            accountcode = did_accountcode[0][1]
        if accountcode > 0:
            with transaction.atomic():
                cdr.accountcode = accountcode
                cdr.save()
        elif cdr.duration > 0:
            if cdr.direction == 1: #incoming, tickets for billing
                if call_trunk in lost_incoming_calls_by_trunk:
                    lost_incoming_calls_by_trunk[call_trunk] += estimated_call_cost
                else:
                    lost_incoming_calls_by_trunk[call_trunk] = estimated_call_cost
            if did: #make a ticket for porting
                if did in lost_calls_by_did:
                    lost_calls_by_did[did] += estimated_call_cost
                else:
                    lost_calls_by_did[did] = estimated_call_cost
    if create_tickets: #make a ticket with the top offenders
        if len(lost_incoming_calls_by_trunk) > 0: 
            text = 'Incoming calls on the following trunk(s) cannot be accounted for! Please add them to the accounting system:\n\n'
            for line in sorted(lost_incoming_calls_by_trunk.items(), reverse=True, key=lambda kv: kv[1]):
                text += line[0]+' $%.2f' % line[1]+'\n'
            data = {'ticket':{
                'type': 'Task',
                'requester_id': 391252079,
                'group_id': 21968609,
                'subject': 'Unaccounted Inbound Trunks',
                'comment':{'body':text}}}
            payload = json.dumps(data)
            url = 'https://cdr_accounting.zendesk.com/api/v2/tickets.json?async=true'
            headers = {'content-type': 'application/json'}
            logger.info(requests.post(url, data=payload, auth=('tickets+api@localhost/token', '*****'), headers=headers))
        if len(lost_outgoing_calls_by_trunk) > 0: 
            text = 'Outgoing calls on the following trunk(s) cannot be accounted for! Please add the account codes to our SIP Proxies:\n\n'
            for line in sorted(lost_outgoing_calls_by_trunk.items(), reverse=True, key=lambda kv: kv[1]):
                text += line[0]+' $%.2f' % line[1]+'\n'
            data = {'ticket':{
                'type': 'Task',
                'requester_id': 391252079,
                'group_id': 22033085,
                'subject': 'Unaccounted Outbound Trunks',
                'comment':{'body':text}}}
            payload = json.dumps(data)
            url = 'https://cdr_accounting.zendesk.com/api/v2/tickets.json?async=true'
            headers = {'content-type': 'application/json'}
            logger.info(requests.post(url, data=payload, auth=('tickets+api@localhost/token', '*****'), headers=headers))
        if len(lost_calls_by_did) > 0: 
            text = 'Calls on these DID(s) cannot be accounted for! Pleases ensure they are fulled ported away or added to our accounting system:\n\n'
            for line in sorted(lost_calls_by_did.items(), reverse=True, key=lambda kv: kv[1]):
                text += line[0]+' $%.2f' % line[1]+'\n'
            data = {'ticket':{
                'type': 'Task',
                'requester_id': 391252079,
                'group_id': 22590215,
                'subject': 'Unaccounted DIDs',
                'comment':{'body':text}}}
            payload = json.dumps(data)
            url = 'https://cdr_accounting.zendesk.com/api/v2/tickets.json?async=true'
            headers = {'content-type': 'application/json'}
            logger.info(requests.post(url, data=payload, auth=('tickets+api@localhost/token', '*****'), headers=headers))
    return('Accountcoding complete.')

@app.task
def bill_all_accounts():
    import datetime, json
    from cdr_rates.models import Rate
    def bill_account(accountcode):
        from dateutil.relativedelta import relativedelta
        import requests
        month = datetime.datetime.now()-relativedelta(months=1)
        month = month.strftime('%Y-%m')
        result = requests.get('http://localhost/cdr-rates/kapi?month='+month+'&accountcode='+str(accountcode)).json()
        return(result)
    accountcoder()
    call_charges = 0
    call_overages = 0
    for rate in Rate.objects.all():
        result = bill_account(rate.accountcode)
        if result is not None:
            logger.info(result)
            call_charges += float(result['call_charges'])
            call_overages += float(result['call_overages'])
    return('\nTotal Call Charges: %.2f' % call_charges+'\nTotal Call Overages: %.2f' % call_overages+'\n')

@app.task
def accountcoder_make_ticket():
    return(accountcoder(create_tickets=True))
