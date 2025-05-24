from elibrary_parser.OrganizationParser import ParserOrg


data_path = "/home/platon/Documents/Parser/org_data"

parser = ParserOrg(org_id="17503", data_path=data_path, date_from=2020, date_to=2021)
# parser.find_publications()
parser.parse_publications()
parser.save_publications_to_csv()

print(f"Done. Total publications: {len(parser.publications)}.")