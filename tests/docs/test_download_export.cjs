const {test}=require('node:test');
const assert=require('node:assert/strict');
const M=require('../../doc/source/_static/economy-model.js');
const C=require('../../doc/source/_static/economy-charts.js');

test('MRIO CSV keeps units and provenance without republishing chart reference values',()=>{
 const recipe={source:'EXIOBASE',release:'3.11.2',table:'IOT',parser_options:{system:'ixi'},year:2024,
   source_url:'https://example.org/release',license_url:'https://example.org/terms',attribution:'EXIOBASE consortium'};
 const row={database:'EXIOBASE',version:M.version(recipe),year:2024,country:'ITA',value:2500000000,unit:'current US$',basis:'GDP at market prices'};
 const state={metric:'gdp',country:'ITA',section:'all'};
 const scale={factor:1e9,unit:'current US$ billion'};
 const result=M.exportRows([row,{...row,database:'EDGAR',value:999},{...row,database:'World Bank',value:888}],[{recipe}],state,scale,C);
 assert.equal(result.length,1);assert.equal(result[0].value,2.5);
 assert.equal(result[0].unit,scale.unit);assert.equal(result[0].source_license_url,recipe.license_url);
 assert.equal(result[0].attribution,recipe.attribution);assert(!('raw_value' in result[0]));
 assert(!('gwp_basis' in result[0]));
});

test('Python example declares the source licence and its scope of reproduction',()=>{
 const recipe={label:'Example',source:'Example',year:2024,parser:'parse_exiobase',parser_options:{system:'ixi'},
   source_url:'https://example.org/release',license_url:'https://example.org/terms',attribution:'Example authors',
   expected_units:{},value_added_rows:[],currency:'USD',currency_scale:1e6};
 const text=M.pythonStart({recipe,regions:[]},{metric:'gdp',country:'world',section:'all'},{});
 assert(text.includes(recipe.license_url));assert(text.includes(recipe.attribution));
 assert(text.includes('not an exact reproduction'));assert(text.includes('import mario'));
});

test('Derived monetary and per-capita exports credit the exchange-rate and population providers',()=>{
 const recipe={source:'EXIOBASE',release:'3.11.2',table:'IOT',parser_options:{system:'ixi'},currency:'EUR',year:2024};
 const row={database:'EXIOBASE',version:M.version(recipe),year:2024,country:'ITA',value:25};
 const result=M.exportRows([row],[{recipe}],{metric:'gdp',country:'ITA',section:'all',perCapita:true},{factor:1,unit:'current US$/person'},C)[0];
 assert.match(result.additional_inputs,/World Bank.*exchange rates.*population/);
 assert.match(result.additional_input_terms,/worldbank/);
 const older={...recipe,year:1996},observation={...row,year:1996};
 const old=M.exportRows([observation],[{recipe:older}],{metric:'gdp',country:'ITA',section:'all'},{factor:1,unit:'current US$'},C)[0];
 assert.match(old.additional_inputs,/Eurostat/);assert(!old.additional_inputs.includes('World Bank'));
});
