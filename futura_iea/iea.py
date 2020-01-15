import pandas as pd
import country_converter as coco
from futura.loader import FuturaLoader
from futura import w
from futura.utils import create_filter_from_description
from futura.markets import FuturaMarket

from collections import OrderedDict

DEFAULT_URL = r"https://iea.blob.core.windows.net/assets/ad1e0f99-8473-463e-a086-994255022195/Archive_Table_Revised.xlsx"
DEFAULT_SHEETNAME = 'Data2'

cc = coco.CountryConverter()

class IEA_Importer:
    def __init__(self, loader, filepath=None, sheetname=None, auto=True):

        assert isinstance(loader, FuturaLoader), 'A FuturaLoader object is required'

        self.loader = loader

        if filepath:
            self.filepath = filepath
        else:
            self.filepath = DEFAULT_URL

        if sheetname:
            self.sheetname = sheetname
        else:
            self.sheetname = DEFAULT_SHEETNAME

        self.keep_dict = {"COAL": "Coal",
                          "OIL": "Oil",
                          "NATGAS": "Natural Gas",
                          "COMBREN": "Combustible Renewables",
                          "COMBNREN": "Other Combustibles",
                          "NUCLEAR": "Nuclear",
                          "HYDRO": "Hydro",
                          "WIND": "Wind",
                          "SOLAR": "Solar",
                          "GEOTHERM": "Geothermal",
                          "OTHERREN": "Other Renewables",
                          "NONSPEC": "Non-Specified",
                          "TOTIMPSB": "Imports"
                          }

        self.df = None
        self.aggregated_data = None
        self.formatted_data = None
        self.all_locations = None

        if auto:
            self.get_iea_data()

    def get_iea_data(self):

        xl = pd.ExcelFile(self.filepath)

        # parse the IEA data into a usable dataframe

        df = xl.parse(self.sheetname, header=1)

        df = df.drop(df.columns[1], axis=1)
        df = df.drop(df.columns[2], axis=1)

        # rename the columns for ease
        indexes = ['Country/Region', 'Source']
        for n, c in enumerate(df.columns[:]):
            if n <= 1:
                df = df.rename(columns={c: indexes[n]})
            else:
                try:
                    df = df.rename(columns={c: pd.to_datetime(c).strftime("%b %Y")})
                except:
                    pass

        df['Source'] = df["Source"].str.split(".", n=1, expand=True)[1]

        # only keep sources in the keep_dict keys and rename to a sensible name
        df = df[df['Source'].isin(list(self.keep_dict.keys()))]
        df['Source'] = df['Source'].apply(lambda x: self.keep_dict[x])

        # calculate the total production for the past 12 months
        df['Latest Year Total'] = df.iloc[:, -12:].sum(axis=1)

        # Get the unique countries from the data
        countries = df['Country/Region'].unique()

        # convert the country names into ecoinvent compliant names


        # deal with the special ones first
        iea_country_convert = {
            'AUSTRALI': 'Australia',
            'NETHLAND': 'Netherlands',
            'SWITLAND': 'Switzerland',
            'UK': 'United Kingdom'
        }

        converted_countries = [iea_country_convert.get(x, x) for x in countries]

        converted_countries_list = [x for x in cc.convert(converted_countries, to='iso2', not_found='not found') if
                                    x != 'not found']

        country_conversion_dict = {x: cc.convert(x, to='iso2', not_found='not found')
                                   if cc.convert(x, to='iso2', not_found='not found') != 'not found'
                                   else cc.convert(iea_country_convert.get(x, x), to='iso2', not_found=None)
                                   for x in countries}

        # convert the countries in the dataframe
        df['Country/Region'] = df['Country/Region'].apply(lambda x: country_conversion_dict[x])

        # aggregate the energy data

        step1 = df.groupby(['Country/Region', 'Source']).agg({'Latest Year Total': 'sum'})

        step2 = step1.groupby(level=0).apply(lambda x: x / float(x.sum()))

        self.df = df
        self.aggregated_data = step2
        self.formatted_data = step2.style.format('{0:,.2%}')

        self.all_locations = converted_countries_list

    def update_grid(self, grid_locations = None):

        if not grid_locations:
            grid_locations = self.all_locations

        if isinstance(grid_locations, str):
            grid_locations = [grid_locations]

        assert isinstance(grid_locations, list)

        #get electricity market(s)

        elec_filter_base = [
            {'filter': 'equals', 'args': ['unit', 'kilowatt hour']},
            {'filter': 'startswith', 'args': ['name', 'market for electricity, high voltage']},
            {'filter': 'doesnt_contain_any', 'args': ['name', ['Swiss Federal Railways', 'label-certified']]},
            {'filter': 'either', 'args':
                [{'filter': 'equals', 'args': ['location', x]} for x in grid_locations]
             }
        ]

        elec_filter = create_filter_from_description(elec_filter_base)

        elec_list = list(w.get_many(self.loader.database.db, *elec_filter))

        # get exchanges to categorise

        exchange_filter = [{'filter': 'equals', 'args': ['unit', 'kilowatt hour']},
                           {'filter': 'exclude', 'args': [
                               {'filter': 'startswith', 'args': ['name', 'market ']},
                           ]},
                           ]
        wurst_exchange_filter = create_filter_from_description(exchange_filter)
        full_exchange_list = []
        for x in elec_list:
            full_exchange_list.extend(list(w.get_many(x['exchanges'], *wurst_exchange_filter)))

        exchange_names = set([x['name'] for x in full_exchange_list])

        convert_dict = OrderedDict()
        convert_dict["import"] = "Imports"
        convert_dict.update(
            {
                "coal": "Coal",
                "lignite": "Coal",
                "oil": "Oil",
                "natural gas": "Natural Gas",
                "wood": "Combustible Renewables",
                "biogas": "Combustible Renewables",
                "peat": "Other Combustibles",
                "blast furnace gas": "Other Combustibles",
                "nuclear": "Nuclear",
                "hydro": "Hydro",
                "wind": "Wind",
                "solar": "Solar",
                "geothermal": "Geothermal",
            })

        # translate all exchanges to their IEA equivalents

        exchange_dict = {}
        for e in exchange_names:
            found = False
            for n in convert_dict.keys():
                if n in e:
                    exchange_dict[e] = convert_dict[n]
                    found = True
                    break

            if not found:
                exchange_dict[e] = 'Non-Specified'

        last_fm = None

        for market in elec_list:

            stratification_dict = self.aggregated_data.xs(market['location'][:2]).to_dict()['Latest Year Total']
            fm = FuturaMarket(market, self.loader.database)

            # create a dataframe of market production volumes by exchange
            pv_df = pd.DataFrame(
                [{'input': k, 'production volume': v['production volume']} for k, v in fm.process_dict.items()])

            # add a Group column to classify each exchange to an IEA type
            pv_df['Group'] = pv_df['input'].apply(lambda x: exchange_dict.get(x, None))

            grand_total = pv_df['production volume'].sum()

            # figure out how to stratify the data based on the proportion of production within IEA groups
            stratification_data = {}

            for g, v in pv_df.groupby('Group'):
                this_total = v['production volume'].sum()
                stratification_data[g] = {}

                # print(v)
                for row_index, row in v.iterrows():
                    if this_total != 0:
                        stratification_data[g][row['input']] = row['production volume'] / this_total
                    else:
                        stratification_data[g][row['input']] = 0

            # multiply these proportions by the actual new grid mix sections
            actual_stratification = {k: v * grand_total for k, v in stratification_dict.items()}

            final_dict = {}

            for k, v in stratification_data.items():
                this_pv = actual_stratification[k]
                for x, n in v.items():
                    final_dict[x] = n * this_pv

            # apply the new numbers to the FuturaMarket

            for k, v in final_dict.items():
                fm.set_pv(k, v)

            fm.relink()

            print('Updated grid mix for {}'.format(cc.convert(market['location'], to="short_name")))


def say_hello():
    print('Hello from the IEA plugin')


def main():
    pass
