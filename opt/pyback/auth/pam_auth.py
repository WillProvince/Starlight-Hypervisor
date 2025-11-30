"""
PAM Authentication Module

Provides integration with Linux PAM (Pluggable Authentication Modules)
to authenticate users against system credentials.
"""

import logging
import pwd
import grp

logger = logging.getLogger(__name__)

# Import Debian's python3-pam package (provides 'PAM' module)
try:
    import PAM
    PAM_AVAILABLE = True
except ImportError:
    PAM_AVAILABLE = False
    logger.warning("python3-pam not available. Install with: sudo apt install python3-pam")


def authenticate_user(username: str, password: str) -> bool:
    """
    Authenticate a user using PAM.
    
    Args:
        username: The username to authenticate
        password: The password to check
        
    Returns:
        bool: True if authentication successful, False otherwise
    """
    if not PAM_AVAILABLE:
        logger.error("PAM authentication is not available (python3-pam not installed)")
        return False
    
    try:
        def pam_conv(auth, query_list, userData):
            """Conversation function for PAM - provides the password"""
            resp = []
            for query, qtype in query_list:
                if qtype == PAM.PAM_PROMPT_ECHO_OFF:
                    # Password prompt
                    resp.append((password, 0))
                elif qtype == PAM.PAM_PROMPT_ECHO_ON:
                    # Username prompt
                    resp.append((username, 0))
                elif qtype in (PAM.PAM_ERROR_MSG, PAM.PAM_TEXT_INFO):
                    # Info/error messages
                    resp.append(('', 0))
                else:
                    return None
            return resp
        
        # Use Debian PAM API
        auth = PAM.pam()
        auth.start('login')  # Use 'login' service
        auth.set_item(PAM.PAM_USER, username)
        auth.set_item(PAM.PAM_CONV, pam_conv)
        
        try:
            auth.authenticate()
            auth.acct_mgmt()  # Account management check
            logger.info(f"PAM authentication successful for user: {username}")
            return True
        except PAM.error as resp:
            logger.warning(f"PAM authentication failed for user: {username} - {resp}")
            return False
                
    except Exception as e:
        logger.error(f"Error during PAM authentication for user {username}: {e}")
        return False


def user_exists(username: str) -> bool:
    """
    Check if a system user exists.
    
    Args:
        username: The username to check
        
    Returns:
        bool: True if user exists, False otherwise
    """
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False


def get_user_info(username: str) -> dict:
    """
    Get information about a system user.
    
    Args:
        username: The username to query
        
    Returns:
        dict: User information including uid, gid, home, shell
        None if user doesn't exist
    """
    try:
        user = pwd.getpwnam(username)
        return {
            'username': user.pw_name,
            'uid': user.pw_uid,
            'gid': user.pw_gid,
            'home': user.pw_dir,
            'shell': user.pw_shell,
            'gecos': user.pw_gecos
        }
    except KeyError:
        return None


def get_user_groups(username: str) -> list:
    """
    Get all groups a user belongs to.
    
    Args:
        username: The username to query
        
    Returns:
        list: List of group names
    """
    try:
        user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        # Also add the user's primary group
        try:
            user = pwd.getpwnam(username)
            primary_group = grp.getgrgid(user.pw_gid).gr_name
            if primary_group not in user_groups:
                user_groups.insert(0, primary_group)
        except (KeyError, AttributeError):
            pass
        return user_groups
    except Exception as e:
        logger.error(f"Error getting groups for user {username}: {e}")
        return []


def is_user_in_group(username: str, groupname: str) -> bool:
    """
    Check if a user is in a specific group.
    
    Args:
        username: The username to check
        groupname: The group name to check
        
    Returns:
        bool: True if user is in the group, False otherwise
    """
    try:
        group = grp.getgrnam(groupname)
        return username in group.gr_mem or pwd.getpwnam(username).pw_gid == group.gr_gid
    except (KeyError, AttributeError):
        return False
