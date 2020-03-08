from cdr_rates.models import CDR

class CDRRouter(object):
    def db_for_write(self, model, **hints):
        if model == CDR:
            return None
        return None
    def db_for_read(self, model, **hints):
        if model == CDR:
            return 'cdr-pusher'
        return None