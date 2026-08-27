# Media File Symlinks

Generated: 2026-06-10 13:08

## What happened

Large media files (videos, images, etc.) have been moved out of this git
repository to avoid exceeding GitHub's 100 MB file size limit.

They now live in an external storage location (pCloud) and each original
`media/` folder inside the repo has been replaced with a **symlink** pointing
to the corresponding folder in that external storage.

Git commits the symlink (just a path pointer) — not the files themselves.

## Storage location

All media files are stored under:
```
/home/john/pCloudDrive/strollopia_org_data
```

The folder structure mirrors the repo exactly:
```
org-data/<project-domain>/<map-name>/media/<file>
```

## First-time setup (restoring symlinks on a new machine)

1. **Install and sign in to [pCloud Drive](https://www.pcloud.com/download-free-online-cloud-storage.html)**
   The drive should mount so that `/home/john/pCloudDrive/strollopia_org_data` is accessible.

    **remember to set the virtual environment: source env/bin/activate**

2. **Run the setup script** from the repo root to recreate all symlinks:

   ```bash
   python migrate_media_to_pcloud.py . <destination_root> --relink-only
   ```

   Or recreate them manually — for each entry below:
   ```bash
   ln -s <destination> <source_symlink>
   ```

3. **Verify** a symlink is working:
   ```bash
   ls -la org-data/<domain>/<map>/media
   ```
   You should see an arrow (`->`) pointing to the pCloud path.

## Migrated folders

### `org-data/climate-stories.strollopia.com/climate-map/media`
- **Symlink:** `/home/john/strollopia_git_hub/strollopia-org-setup/org-data/climate-stories.strollopia.com/climate-map/media`
- **Destination:** `/home/john/pCloudDrive/strollopia_org_data/org-data/climate-stories.strollopia.com/climate-map/media`
- **Files (13):**
  - `1.png`
  - `1B585F1E-21EF-4627-89C8-F82985C81BA9_-_downloaded_from_my_phone.jpeg`
  - `As_The_River_Bends_Video.MP4`
  - `DJI_0039.JPG`
  - `Eos_Store_Front.jpg`
  - `FullSizeRender.jpeg`
  - `IMG_1847_98mUIRy.jpeg`
  - `IMG_3799.jpeg`
  - `Lorax.jpg`
  - `Olde_Furrow_Farm.mp4`
  - `Piecemeal.mp4`
  - `WFM.jpeg`
  - `logo-transparent.png`

### `org-data/kentville.strollopia.com/business-map/media`
- **Symlink:** `/home/john/strollopia_git_hub/strollopia-org-setup/org-data/kentville.strollopia.com/business-map/media`
- **Destination:** `/home/john/pCloudDrive/strollopia_org_data/org-data/kentville.strollopia.com/business-map/media`
- **Files (165):**
  - `AG_Custom_Apparel.jpg`
  - `Acadia_Refrigeration_AC_Ltd.jpg`
  - `Affordable_Freight_Consultants.jpg`
  - `Allied_Insurance.jpg`
  - `Ametora_Supply.jpg`
  - `Anderson_Sinclair.jpg`
  - `Annapolis_Blossom_Gallery_Consignment.jpg`
  - `Annapolis_Valley_Apple_Blossom_Festival.jpg`
  - `Annapolis_Valley_Mountain_Biking_Association.jpg`
  - `Annapolis_Valley_Radio.jpg`
  - `Annapolis_Valley_Surveys.jpg`
  - `Apple_Valley_Foods_Inc.jpg`
  - `Arbour_Square_Osteopathy.jpg`
  - `Armour_Transportation_Systems.jpg`
  - `BTW_Law.jpg`
  - `Back_and_Neck_Pain_Relief_Center.jpg`
  - `Bloom_Box.jpg`
  - `Blue_50_Nails.jpg`
  - `Brackish_Biomechanical_Bracing.jpg`
  - `Brads_Decor_Centre.jpg`
  - `Bricks_and_Birches.jpg`
  - `Bridge_Beauty_Bar.jpg`
  - `Buddens_Appliance_Services.jpg`
  - `Butts_Auto_Service.jpg`
  - `Capital_Paper_Products_Inc.jpg`
  - `CentreStage_Theatre.jpg`
  - `Chicken_Farmers_of_Nova_Scotia.jpg`
  - `Child_Youth_Mental_Health_Addiction_Services.jpg`
  - `Chrysalis_House_Association.jpg`
  - `Clannad_Counselling_Consulting.jpg`
  - `Cleveland_Carpet_One_Floor_Home.jpg`
  - `Community_Living_Alternative_Society.jpg`
  - `Computerized_Business_Solutions_Inc.jpg`
  - `Crave_Studio.jpg`
  - `Creative_Management_Solutions.jpg`
  - `Crown_Fibre_Tube_Inc.jpg`
  - `DM_Reid_Jewellers.jpg`
  - `Davids_Eyewear_Ltd.jpg`
  - `Dayan_Sushi.jpg`
  - `Edward_Jones.jpg`
  - `Enve_Hair_Salon.jpg`
  - `Equilibrium_Engineering.jpg`
  - `Evangeline_Wealth.jpg`
  - `Family_Tire_Ltd.jpg`
  - `Farm_Credit_Canada.jpg`
  - `Foodland_Kentville.jpg`
  - `Freedom_Miniatures.jpg`
  - `Glimpse_Hair_Esthetics.jpg`
  - `Golding_Associates.jpg`
  - `Grant_Thornton_LLP.jpg`
  - `Greenfields_Indoor_Air_Solutions.jpg`
  - `Griffin_Sales_Service_Ltd.jpg`
  - `Guardian_Centennial_Pharmacy.jpg`
  - `Half_Acre_Cafe.jpg`
  - `Hants_Kings_Business_Development_Centre.jpg`
  - `Harvest_Wealth_Management.jpg`
  - `Hawthorn_Clinic.jpg`
  - `Headliners_Studio.jpg`
  - `Healing_Hands.jpg`
  - `Herrit_Income_Tax_Ltd.jpg`
  - `Huntleys_Sub-Aqua_Construction.jpg`
  - `Jill_Forse_Traditional_Chinese.jpg`
  - `Kent_Duffett.jpg`
  - `Kentville_After_School_Program.jpg`
  - `Kentville_Chiropractic.jpg`
  - `Kentville_Chrysler_Dodge_Jeep.jpg`
  - `Kentville_Dental_Centre_Ltd.jpg`
  - `Kentville_Regional_Library.jpg`
  - `Kentville_Volunteer_Fire_Department.jpg`
  - `Kevin_Martin_Accounting.jpg`
  - `Kings_Arms_Pub.jpg`
  - `Kings_County_Museum.jpg`
  - `Kings_North_MLA.jpg`
  - `Kings_Point-to-Point_Transit.jpg`
  - `LIV_Fashion_Boutique.jpg`
  - `Lawtons.jpg`
  - `Light_Touch_Laser.jpg`
  - `Lisas_Independent_Grocer.jpg`
  - `Little_Pumpkins_Daycare.jpg`
  - `Loonies_Toonies.jpg`
  - `MacLeod_Lorway_Insurance.jpg`
  - `Maders_Tobacco_Store_Ltd.jpg`
  - `Marion_Hill_Law_Office.jpg`
  - `Maritime_Express_Cider.jpg`
  - `Maritime_Travel.jpg`
  - `Maynard_Bent_Fagan.jpg`
  - `Mias_Endless_Pawsabillities_Dog_Grooming.jpg`
  - `Michael_DeLuca_Woodworking.jpg`
  - `Mister_Printer_Ltd.jpg`
  - `Mortgage_Intelligence.jpg`
  - `Murphys_Barber.jpg`
  - `Muttarts_Law_Firm.jpg`
  - `NSLC.jpg`
  - `Nails_by_Paige.jpg`
  - `Natalinos_Pizza.jpg`
  - `Nathanson_Seaman_Watts.jpg`
  - `Needs_Convience_Store.jpg`
  - `New_Scotland_Candle_Company.jpg`
  - `Noel_Co.jpg`
  - `Norths_Collision_Centre.jpg`
  - `Norwood_Health_Associates.jpg`
  - `Nova_Scotia_Works.jpg`
  - `Occasions_Gifts_Décor.jpg`
  - `Open_Arms_Resource_Centre.jpg`
  - `Open_Secrets_Independent_Booksellers.jpg`
  - `Paddys_Pub_Rosies_Restaurant.jpg`
  - `Park_Street_Ultramar.jpg`
  - `Paula_Huntley_Event_Planner.jpg`
  - `Paulines_Golden_Threads.jpg`
  - `Perennia.jpg`
  - `Phantom_Effects.jpg`
  - `Phinneys_Clothing.jpg`
  - `Porters_Custom_Trophy_Engraving.jpg`
  - `RBC_Royal_Bank.jpg`
  - `RD_Chisholm.jpg`
  - `REMAX_Advantage.jpg`
  - `Red_Birch_Media.jpg`
  - `Remys_Nails_Spa.jpg`
  - `Rockwell_Home_Hardware.jpg`
  - `Ross_Graphic.jpg`
  - `Ryan_Roberts_Music.jpg`
  - `Safeguard_Property_Management.jpg`
  - `Scissor_Over_Comb.jpg`
  - `Silver_Horse_Florist.jpg`
  - `Simply_for_Life.jpg`
  - `Skylit.jpg`
  - `Speedpro_Signs_Imaging.jpg`
  - `Sugarhouse_Ceramics.jpg`
  - `TACOcentric.jpg`
  - `TAN_Coffee.jpg`
  - `Taylor_MacLellan_Cochrane_Lawyers.jpg`
  - `Thats_The_Look_Hair_Studio.jpg`
  - `The_Black_Cat_Bookstore.jpg`
  - `The_Co-operators.jpg`
  - `The_Healing_Station.jpg`
  - `The_Portal.jpg`
  - `The_Red_Door.jpg`
  - `The_Ritcey_Team.jpg`
  - `The_Snore_Shop.jpg`
  - `The_Space.jpg`
  - `The_Valley_Care_Pregnancy_Centre.jpg`
  - `Threadbarrow.jpg`
  - `Tides_Contemporary_Art_Gallery.jpg`
  - `Tigers_Eye_Tattoos.jpg`
  - `Total_Energy_Inc.jpg`
  - `Triple_E_Technology_Solutions.jpg`
  - `VANSDA.jpg`
  - `Valley_Bubble_Tea.jpg`
  - `Valley_Child_Development.jpg`
  - `Valley_Community_Learning_Association.jpg`
  - `Valley_Music_Studio.jpg`
  - `Valley_REN.jpg`
  - `Valley_Stove_and_Cycle.jpg`
  - `Valley_Tire.jpg`
  - `Victors_Cut_Barbershop.jpg`
  - `Waterbury_Newton_Law_Firm.jpg`
  - `Webster_Street_Hearing_Boutique.jpg`
  - `Wetmore_Appraisals.jpg`
  - `Wheelhouse_Coffee_Co.jpg`
  - `White_Family_Funeral_Home.jpg`
  - `Wholesum_Refillery.jpg`
  - `Wilsons_Pharmasave.jpg`
  - `Wind_Rose_Web_Design.jpg`
  - `Wink_Eye_Glamour.jpg`
  - `igot_Skate.jpg`

### `org-data/kentville.strollopia.com/mural-map/media`
- **Symlink:** `/home/john/strollopia_git_hub/strollopia-org-setup/org-data/kentville.strollopia.com/mural-map/media`
- **Destination:** `/home/john/pCloudDrive/strollopia_org_data/org-data/kentville.strollopia.com/mural-map/media`
- **Files (26):**
  - `361112759_1448081519350246_691799926509851250_n.jpg`
  - `361160704_624687309636481_6014032663208414190_n.jpg`
  - `361623204_695700865930963_5585190013476748371_n.jpg`
  - `416633b6-6b50-452a-877d-5bec66422acd.jpg`
  - `81058922-3e2a-40ae-b494-7bbde57c5621.jpg`
  - `DAR_Mural.jpg`
  - `IMG_5964.jpg`
  - `a103c5e9-30b8-4391-a97d-bb31bdb582c3.jpg`
  - `alan_syliboy.jpg`
  - `annapolisvalley.jpg`
  - `artisticvisionary.jpg`
  - `bryan_gibson.jpg`
  - `community_crossing.jpg`
  - `daughter_of_community.jpg`
  - `duckmarsh.jpg`
  - `family_resurgence.jpg`
  - `images.jpg`
  - `lostdominion.jpg`
  - `memory_lane_3.jpg`
  - `microsystems.jpg`
  - `miyoshi_kondo.jpg`
  - `noplacelikekentville.jpg`
  - `northernpitcherplant.jpg`
  - `sassy_pants.jpg`
  - `the_wave.jpg`
  - `whispers.jpg`

### `org-data/valleyartmap.strollopia.com/art-map/media`
- **Symlink:** `/home/john/strollopia_git_hub/strollopia-org-setup/org-data/valleyartmap.strollopia.com/art-map/media`
- **Destination:** `/home/john/pCloudDrive/strollopia_org_data/org-data/valleyartmap.strollopia.com/art-map/media`
- **Files (51):**
  - `Acadian-Deportation-Cross-Landscapet-for-VAM-by-John-Robichaud.jpg`
  - `As_The_Tide_Flows.mp3`
  - `As_The_Tide_Flows_Teaser.mp3`
  - `Ayelsford-Mural-4-for-VAM-By-John-Robichaud.jpg`
  - `Aylesford_Mural_Teaser.mp3`
  - `Aylesford_Mural_V2.mp3`
  - `Borden-Monument-for-VAM-by-John-Robichaud.jpg`
  - `Borden_Monument.mp3`
  - `Borden_Monument_Teaser.mp3`
  - `Charles-MacDonald-Concrete-House-for-VAM-by-John-Robichaud.jpg`
  - `Charles_Macdonald_Museum.mp3`
  - `Charles_Macdonald_Museum_Teaser.mp3`
  - `Cross_Teaser.mp3`
  - `DAR_Railway.mp3`
  - `DAR_Teaser.mp3`
  - `Deportation_Cross_YmecXx1.mp3`
  - `Disruptor-for-VAM-by-John-Robichaud.jpg`
  - `Disruptor_Teaser.mp3`
  - `Disruptor_n19CK4O.mp3`
  - `Dominion-Atlantic-Railroad-Station-for-VAM-by-John-Robichaud.jpg`
  - `Dr-Apple-Landscape-for-VAM-by-John-Robichaud.jpg`
  - `Dr._Apple_Teaser.mp3`
  - `Dr._Apple_hKwi3gR.mp3`
  - `Emergency-Exit-for-VAM-by-John-Robichaud.jpg`
  - `Emergency_Exit.mp3`
  - `Emergency_Exit_Teaser.mp3`
  - `Evangeline-Landscape-by-John-Robichaud-for-Valley-Art-Map-3000x2003-sRGB_m4IoLzR.jpg`
  - `Evangeline_Statue.mp3`
  - `Evangeline_Teaser.mp3`
  - `Fountain_of_Grand_Pre.mp3`
  - `Fountain_of_Grand_Pre_Teaser.mp3`
  - `Fountaine-de-Grand-Pre-for-VAM-by-John-Robichaud.jpg`
  - `Indeterminate-Tillage-for-VAM-by-John-Robichaud.jpg`
  - `Indeterminate_Tillage.mp3`
  - `Mona-Parsons-Alt-for-VAM-by-John-Robichaud.jpg`
  - `Mona_Parsons_Teaser.mp3`
  - `Mona_Parsons_V2_1.mp3`
  - `Pasture-Gate-for-VAM-by-John-Robichaud.jpg`
  - `Pasture_Gate.mp3`
  - `Pasture_Gate_Teaser.mp3`
  - `Reeve-Sculpture-for-VAM-by-John-Robichaud.jpg`
  - `That-You-May-Live-for-VAM-by-John-Robichaud.jpg`
  - `That_You_May_Live.mp3`
  - `That_You_May_Live_Teaser.mp3`
  - `The-tide-Flows-for-VAM-by-John-Robichaud.jpg`
  - `The_Stone_Head.mp3`
  - `The_Stone_Head_Teaser.mp3`
  - `Tillage_Teaser.mp3`
  - `Trestle_Teaser.mp3`
  - `Work-At-The-Trestle-for-VAM--by-John-Robichaud.jpg`
  - `Work_at_the_Trestle_iANcxW8.mp3`

### `org-data/wolfville.strollopia.com/downtown/media`
- **Symlink:** `/home/john/strollopia_git_hub/strollopia-org-setup/org-data/wolfville.strollopia.com/downtown/media`
- **Destination:** `/home/john/pCloudDrive/strollopia_org_data/org-data/wolfville.strollopia.com/downtown/media`
- **Files (39):**
  - `102_4528_preview.jpeg`
  - `20190804_091626.jpg`
  - `32248_127572790597575_351275_n.jpg`
  - `67494238_2368444100112097_9027195548729344000_n_yCipkUG.jpg`
  - `Blomidon_Inn.jpg`
  - `Blueberry_and_Strawberry_cones_Jan_2019_2.jpg`
  - `ChartsPhotos-7.jpg`
  - `Cochranes_Photo_1.jpg`
  - `Copy_of_20170328-354-2D.jpg`
  - `DRMF-2017-Dienes-Friday-Web-9703-640x640.jpg`
  - `David_demo.JPG`
  - `Ginger_048.jpg`
  - `Herbin_Mural.jpeg`
  - `Homefires_1.jpg`
  - `IMG_7122.JPG`
  - `IMG_7137_hH3LRdJ.JPG`
  - `IMG_7153_hVFl2Ew.JPG`
  - `IMG_7162.JPG`
  - `IMG_7163.JPG`
  - `IMG_7183_c7XIYib.JPG`
  - `IMG_7199.JPG`
  - `IMG_7216.JPG`
  - `IMG_7224.JPG`
  - `IMG_7408.jpg`
  - `IMG_7480_oQDJDq5.JPG`
  - `IMG_8702.jpeg`
  - `Jeff_Customer_LOngspell.JPG`
  - `JuniperNov2019-157.jpg`
  - `Staff_Photo_May_2019.jpg`
  - `Store-2.jpg`
  - `Tattingstone_Inn.jpeg`
  - `Typical_1_Bedroom_Suite.png`
  - `building.jpg`
  - `cropped_front_of_church.jpg`
  - `front_of_spa.jpg`
  - `harvestgallery.jpg`
  - `paddys.jpg`
  - `roselawn_lodging_sign.JPG`
  - `sup_king.JPG`
