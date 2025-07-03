import driver as LCD_2inch

disp = LCD_2inch.LCD_2inch()
disp.Init()
disp.clear()
disp.bl_DutyCycle(0)