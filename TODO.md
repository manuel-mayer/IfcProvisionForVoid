# TODO List for IfcProvisionForVoid

- [x] match ifcGuid across different file names, so no duplicated Guids
- [x] give user options for pset and parameter names when database is written back to ifc
- [x] write building storey to the database after filename
- [ ] display database statistic: percent of approved per building storey
- [ ] test with multiple ifc files for H,L,S,E
- [ ] test with existing database, multiple iterations
- [ ] test ifc2x3, ifc4 and ifc4x3
- [ ] test with bigger project > 500 objects
- [ ] test pset and attribute name for writeback
- [ ] make bulk approval field accept excel files, always use first table in excel file 
- [ ] check hosting options for database
- [ ] check import export options for revit with dynamo for approval status
- [ ] integrate comment field for architecture and structure
- [ ] option to purge database of objects that are flagged as deleted

separate app perhaps: provisionforvoids need to know if structurally relevant
- [ ] bbox center point inside aligned boundingbox of structural elements: walls, slabs, beams
- [ ] output just structural host= true/false or void host= IfcWall: LoadBearing and IfcWall
- [ ] bonus: write wall material to provision for void for tendering quantification