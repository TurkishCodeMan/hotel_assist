import os
from datetime import datetime, timezone
import yaml
from textwrap import wrap


# for loading configs to environment variables
def load_config(file_path):
    # Define default values
    default_values = {
        'SERPER_API_KEY': 'default_serper_api_key',
        'OPENAI_API_KEY': 'default_openai_api_key',
        'SERPER_API_KEY': 'default_groq_api_key',
    }
    
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            # If the value is empty or None, load the default value
            if not value:
                os.environ[key] = default_values.get(key, '')
            else:
                os.environ[key] = value
# def load_config(file_path):
#     with open(file_path, 'r') as file:
#         config = yaml.safe_load(file)
#         for key, value in config.items():
#             os.environ[key] = value

# for getting the current date and time in UTC
def get_current_utc_datetime():
    now_utc = datetime.now(timezone.utc)
    current_time_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")
    return current_time_utc

# for checking if an attribute of the state dict has content.
def check_for_content(var):
    if var:
        try:
            var = var.content
            return var.content
        except:
            return var
    else:
        var


# def custom_print(message, stdscr=None):
#     if stdscr:
#         max_y, max_x = stdscr.getmaxyx()
#         max_y -= 2  # Leave room for a status line at the bottom

#         lines = message.split("\n")
#         for line in lines:
#             wrapped_lines = wrap(line, max_x)
#             for wrapped_line in wrapped_lines:
#                 current_y, current_x = stdscr.getyx()
#                 if current_y >= max_y:
#                     stdscr.addstr(max_y, 0, "-- More --")
#                     stdscr.refresh()
#                     key = stdscr.getch()  # Wait for user to press a key

#                     if key == ord('q'):
#                         stdscr.clear()
#                         stdscr.addstr(0, 0, "Exiting...")
#                         stdscr.refresh()
#                         return

#                     stdscr.clear()
#                     current_y = 0

#                 stdscr.addstr(current_y, 0, wrapped_line[:max_x])
#                 stdscr.addstr(current_y + 1, 0, "")  # Move to the next line
#                 stdscr.refresh()

#         stdscr.refresh()
#     else:
#         print(message)

def custom_print(message, stdscr=None, scroll_pos=0):
    if stdscr:
        max_y, max_x = stdscr.getmaxyx()
        max_y -= 2  # Leave room for a status line at the bottom

        wrapped_lines = []
        for line in message.split("\n"):
            wrapped_lines.extend(wrap(line, max_x))

        num_lines = len(wrapped_lines)
        visible_lines = wrapped_lines[scroll_pos:scroll_pos + max_y]

        stdscr.clear()
        for i, line in enumerate(visible_lines):
            stdscr.addstr(i, 0, line[:max_x])

        stdscr.addstr(max_y, 0, f"Lines {scroll_pos + 1} - {scroll_pos + len(visible_lines)} of {num_lines}")
        stdscr.refresh()

        return num_lines
    else:
        print(message)


def create_tool_description(tools=None):
     # Araçların dinamik açıklamasını oluştur
        tools_description = "Kullanabileceğin araçları aşağıda listeliyorum. Bu araçları kullanarak rezervasyon işlemlerini yerine getirebilirsin:\n\n"
        
        if tools:
            for i, tool in enumerate(tools, 1):
                tools_description += f"{i}. {tool.name} - {tool.description}\n"
                
                # Parametre detayları
                if hasattr(tool, 'inputSchema') and tool.inputSchema and 'properties' in tool.inputSchema:
                    tools_description += "   Parametreler:\n"
                    required_params = tool.inputSchema.get('required', [])
                    
                    for param_name, param_details in tool.inputSchema['properties'].items():
                        is_required = param_name in required_params
                        param_type = param_details.get('type', '')
                        param_desc = param_details.get('description', '')
                        
                        # Örnek değer oluştur
                        example = ''
                        if param_type == 'string':
                            if param_name == 'customer_name':
                                example = '"Ali Veli"'
                            elif param_name == 'check_in_date' or param_name == 'check_out_date':
                                example = '"2025-06-20"'
                            elif param_name == 'room_type':
                                example = '"Deluxe"'
                            elif param_name == 'reservation_id':
                                example = '"12345"'
                            else:
                                example = '"örnek"'
                        elif param_type == 'integer':
                            if param_name == 'adults':
                                example = '2'
                            elif param_name == 'children':
                                example = '1'
                            else:
                                example = '0'
                        elif param_type == 'boolean':
                            example = 'true'
                            
                        required_text = "(zorunlu)" if is_required else "(opsiyonel)"
                        tools_description += f"   - {param_name} {required_text} (ör: {example})"
                        if param_desc:
                            tools_description += f" - {param_desc}"
                        tools_description += "\n"
                tools_description += "\n"
        else:
            tools_description += "Şu an kullanılabilir araç bulunmamaktadır.\n"
            
        tools_description += "Müşterinin talebi doğrultusunda uygun aracı seç ve kullan. Eğer araç kullanımı gerekli değilse, bilgiyi doğrudan sağla."
        return tools_description