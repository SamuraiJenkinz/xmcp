import { ArrowDownloadRegular } from '@fluentui/react-icons';
import {
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
  MenuButton,
} from '@fluentui/react-components';

interface ExportMenuProps {
  onExportMarkdown: () => void;
  disabled?: boolean;
}

export function ExportMenu({ onExportMarkdown, disabled = false }: ExportMenuProps) {
  return (
    <Menu>
      <MenuTrigger disableButtonEnhancement>
        <MenuButton
          appearance="subtle"
          icon={<ArrowDownloadRegular />}
          aria-label="Export conversation"
          disabled={disabled}
        >
          Export
        </MenuButton>
      </MenuTrigger>
      <MenuPopover>
        <MenuList>
          <MenuItem onClick={onExportMarkdown}>Markdown (.md)</MenuItem>
          {/* Future: JSON format from EXPT-05 */}
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}
