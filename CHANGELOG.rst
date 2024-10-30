****************
Release History
****************

v 0.3.4
-------

Parsing functions error fixed
~~~~~~~~
Recent pandas versions have changed the way they interpret "None" in DataFrames indices and values, which are currently interpreted it as NaN. 
This mario update fixes the issue by replacing NaN with the string "None" when parsing excel files.

Deprecated functions
~~~~~~~~
Parser for old-fashioned Eurostat SUTs is deprecated. This function relied on peculiarly structured SUTs formats.
In case you need to parse such SUTs, please rearrange them into the standard MARIO format.
You can check the MARIO format from 'SUT.xlsx' file in the mario/test directory in this repository.


v 0.3.3
-------

Settings
~~~~~~~~
to_excel function bug in flow mode fixed.


v 0.3.0
-------

Settings
~~~~~~~~

New functionalities are provided to allow the user to change some naming convensions in mario indexing and input-output nomenclature convensions in mario.

Isard to Chenery-Moses Transformation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The transformation implies moving from trades accounted in the USE matrix to trades accounted in the SUPPLY matrix.

Data Templates
~~~~~~~~~~~~~~

New functionalities are added to create an enpty IO/SU tables  from tabular data.

Figaro Parser
~~~~~~~~~~~~~

New download and parsing functionalities are added to parser figaro database.


Table Downloader
~~~~~~~~~~~~~~~~

Donwload functions are added to the software. Some of the download functions are using pymrio database download functionalities, and some other databases are mario exclusive.

Deprecated functions
~~~~~~~~~~~~~~~~~~~~

is_productive and backup methods are deprecated.

Improvements
~~~~~~~~~~~~

* The add_sector function imprvements are implemented to make the code faster.
* Updating dependencies versioning (specifically pandas, numpy and xlsxwriter) 


Documentation
~~~~~~~~~~~~~

* The tutorials are updated to improve the readiblity and quality of the juputer notebook functionalities.
* New templates for the readthedocs.