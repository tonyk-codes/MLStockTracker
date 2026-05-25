with open(r'e:\Desktop\Project\MLStockTracker\MLStockTracker\css\style.css', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Keep only up to line 556 (index 555)
# Make sure the file ends with a newline
kept = lines[:556]
# Strip trailing blank lines
while kept and kept[-1].strip() == '':
    kept.pop()
kept.append('\n')

with open(r'e:\Desktop\Project\MLStockTracker\MLStockTracker\css\style.css', 'w', encoding='utf-8', newline='\n') as f:
    f.writelines(kept)

print(f'Done. File now has {len(kept)} lines')
