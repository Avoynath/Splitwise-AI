"""Group management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.group import Group, GroupMember
from app.schemas.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupListResponse,
    AddMemberRequest, MemberInfo, GroupSummary,
)

router = APIRouter(prefix="/groups", tags=["Groups"])


def _build_member_info(member: GroupMember, user: User) -> MemberInfo:
    return MemberInfo(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=member.role,
        avatar_url=user.avatar_url,
        joined_at=member.joined_at,
    )


@router.get("", response_model=list[GroupListResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all groups the current user belongs to."""
    result = await db.execute(
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == current_user.id)
        .options(selectinload(Group.members))
        .order_by(Group.created_at.desc())
    )
    groups = result.scalars().unique().all()

    return [
        GroupListResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            type=g.type,
            created_by=g.created_by,
            created_at=g.created_at,
            member_count=len(g.members),
        )
        for g in groups
    ]


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new group and add the creator as admin."""
    group = Group(
        name=data.name,
        description=data.description,
        type=data.type,
        created_by=current_user.id,
    )
    db.add(group)
    await db.flush()

    # Add creator as admin member
    member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="admin",
    )
    db.add(member)
    await db.flush()
    await db.refresh(group)

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        type=group.type,
        created_by=group.created_by,
        created_at=group.created_at,
        members=[_build_member_info(member, current_user)],
        member_count=1,
    )


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a group by ID with members."""
    result = await db.execute(
        select(Group)
        .options(selectinload(Group.members))
        .where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Check membership
    is_member = any(m.user_id == current_user.id for m in group.members)
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    # Build member info
    member_infos = []
    for member in group.members:
        user_result = await db.execute(select(User).where(User.id == member.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            member_infos.append(_build_member_info(member, user))

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        type=group.type,
        created_by=group.created_by,
        created_at=group.created_at,
        members=member_infos,
        member_count=len(member_infos),
    )


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a group (admin only)."""
    result = await db.execute(
        select(Group).options(selectinload(Group.members)).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Check admin
    admin_member = next((m for m in group.members if m.user_id == current_user.id and m.role == "admin"), None)
    if not admin_member:
        raise HTTPException(status_code=403, detail="Only admins can update the group")

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description

    await db.flush()
    await db.refresh(group)

    # Return full response
    return await get_group(group_id, db, current_user)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a group (admin only)."""
    result = await db.execute(
        select(Group).options(selectinload(Group.members)).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    admin_member = next((m for m in group.members if m.user_id == current_user.id and m.role == "admin"), None)
    if not admin_member:
        raise HTTPException(status_code=403, detail="Only admins can delete the group")

    await db.delete(group)


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: int,
    data: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a member to a group by email."""
    # Verify group exists and user is a member
    result = await db.execute(
        select(Group).options(selectinload(Group.members)).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    is_member = any(m.user_id == current_user.id for m in group.members)
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    # Find user by email
    user_result = await db.execute(select(User).where(User.email == data.email))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User with this email not found")

    # Check if already a member
    already_member = any(m.user_id == target_user.id for m in group.members)
    if already_member:
        raise HTTPException(status_code=409, detail="User is already a member of this group")

    member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        role=data.role,
    )
    db.add(member)
    await db.flush()

    return {"message": f"{target_user.name} added to {group.name}"}


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from a group (admin or self)."""
    result = await db.execute(
        select(Group).options(selectinload(Group.members)).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    is_admin = any(m.user_id == current_user.id and m.role == "admin" for m in group.members)
    is_self = current_user.id == user_id

    if not is_admin and not is_self:
        raise HTTPException(status_code=403, detail="Only admins can remove other members")

    member = next((m for m in group.members if m.user_id == user_id), None)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this group")

    await db.delete(member)
